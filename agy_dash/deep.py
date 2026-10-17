"""Deep signal extraction - a second, richer read-only pass over the CLI logs.

`agy_usage.scan()` answers "how many tokens". This module answers "what
happened": tool mix, turnarounds, time budget, failures, denials, model
switches, workspaces, MCP usage, artifacts, inter-agent messages.

Design rules carried over from the handoff doc (section 7):
  * tool names come from `tool_calls[].name` - authoritative; result step
    types are often just GENERIC.
  * tool names are filtered: one transcript contains a corrupted, enormous
    name, so anything that is not a sane identifier is dropped.
  * `transcript_full.jsonl` is preferred (content is not truncated there).
  * gaps are capped (4 h) so a session left open overnight cannot report a
    fake "busy" day. Capped gaps are counted and surfaced.
  * no per-call model, no thinking-token split, no cache-write field, no
    approval wait for granted prompts - those do not exist locally.

Everything here is read-only and never writes into the brain directory.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

GAP_CAP_SECONDS = 4 * 3600
HISTORY_FILE = "history.jsonl"
SETTINGS_FILE = "settings.json"

# A corrupted tool name in one transcript is ~2 KB of prose. Real names are short
# identifiers, so anything else is dropped rather than shown as a "tool".
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

_TS_RE = re.compile(r"(?:Created|Completed) At:\s*([0-9T:\-+]{19,25})")
_SETTING_SWITCH_RE = re.compile(r"The user changed setting `Model Selection` from (.+?) to (.+?)[\r\n`]")
_DENIAL_RE = re.compile(r"permission check failed|was denied|deny rule", re.IGNORECASE)


def _parse_ts(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _valid_tool_name(name) -> bool:
    return bool(isinstance(name, str) and _TOOL_NAME_RE.match(name))


def _failure_text(content, status: str) -> str:
    """First meaningful line of a failure body - never just the status word."""
    if content:
        for line in str(content).splitlines():
            s = " ".join(line.split())
            if (len(s) >= 12 and not s.startswith(("Created At:", "Completed At:"))
                    and any(ch.isalpha() for ch in s)):
                return s[:140]
    return "(no message text)"


def _clean_model_name(name) -> str:
    """Model names are followed by a sentence of boilerplate; keep the name only."""
    return re.split(r"\.\s", str(name))[0].strip().strip("`")[:60]


def _project_name(workspace) -> str:
    ws = str(workspace)
    if "\\" in ws or "/" in ws:
        return Path(ws).name or "(unknown)"
    return "(unknown)"


_EXIT_CODE_RE = re.compile(r"command exited with code (-?\d+)", re.IGNORECASE)
_CANCEL_RE = re.compile(r"was canceled|canceled with result", re.IGNORECASE)


def _command_result(content: str) -> tuple[float | None, int | None, str]:
    """(duration_seconds, exit_code, note) from a command result block.

    The block starts with `Created At:` / `Completed At:` stamps and carries
    `The command exited with code N.` (or a cancellation note). Without that
    marker the block belongs to some other tool, and pairing its stamps with a
    command would invent a duration - so it is rejected instead.
    """
    if not content or "Completed At" not in content:
        return None, None, ""
    canceled = bool(_CANCEL_RE.search(content))
    exit_match = _EXIT_CODE_RE.search(content)
    if not canceled and not exit_match:
        return None, None, ""
    stamps = _TS_RE.findall(content)
    if len(stamps) < 2:
        return None, None, ""
    a, b = _parse_ts(stamps[0]), _parse_ts(stamps[-1])
    if not a or not b:
        return None, None, ""
    duration = (b - a).total_seconds()
    if duration < 0 or duration > GAP_CAP_SECONDS:
        return None, None, "implausible stamp pair, ignored"
    if canceled:
        return duration, None, "canceled"
    return duration, int(exit_match.group(1)), ""


@dataclass
class DeepData:
    scanned_at: datetime
    root: str
    duration_seconds: float
    tool_calls: pd.DataFrame
    turnarounds: pd.DataFrame
    gaps: pd.DataFrame
    failures: pd.DataFrame
    denials: pd.DataFrame
    commands: pd.DataFrame
    model_switches: pd.DataFrame
    session_meta: pd.DataFrame
    step_days: pd.DataFrame
    artifacts: pd.DataFrame
    messages: pd.DataFrame
    counters: dict
    warnings: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.tool_calls.empty and self.session_meta.empty


def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def _read_receipts(path: Path) -> dict:
    """messages/read.json maps message id -> bool."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _transcript(sdir: Path) -> Path | None:
    logs = sdir / ".system_generated" / "logs"
    full = logs / "transcript_full.jsonl"
    if full.exists():
        return full
    plain = logs / "transcript.jsonl"
    return plain if plain.exists() else None


def _load_history(root: Path) -> dict[str, str]:
    """conversationId -> workspace path."""
    hist = root.parent / HISTORY_FILE
    out: dict[str, str] = {}
    if not hist.exists():
        return out
    with hist.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid, ws = o.get("conversationId"), o.get("workspace")
            if cid and ws and cid not in out:
                out[cid] = ws
    return out


def _load_subagent_parents(root: Path) -> dict[str, tuple[str, str]]:
    """subagent conversationId -> (agent type, parent conversationId)."""
    subs: dict[str, tuple[str, str]] = {}
    for parent in root.iterdir():
        d = parent / ".system_generated" / "subagents"
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            try:
                o = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue
            cid = o.get("conversationId")
            if cid:
                desc = o.get("subagentDescriptor") or {}
                subs[cid] = (desc.get("typeName", "subagent"), parent.name)
    return subs


def _current_model(root: Path) -> str | None:
    p = root.parent / SETTINGS_FILE
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text(encoding="utf-8", errors="replace")) or {}).get("model")
    except (json.JSONDecodeError, OSError):
        return None


def _tool_rows(step: dict, sid: str, day: str, step_index):
    """Tool-call rows plus how many corrupt names were dropped."""
    rows = []
    dropped = 0
    for tc in step.get("tool_calls") or []:
        name = tc.get("name")
        if not _valid_tool_name(name):
            dropped += 1
            continue
        args = tc.get("args") or {}
        server = args.get("ServerName") if name == "call_mcp_tool" else None
        command = args.get("CommandLine") if name == "run_command" else None
        rows.append({
            "session_id": sid, "date": day, "step_index": step_index, "tool": name,
            "server": server or "",
            "action": str(args.get("toolAction") or args.get("toolSummary") or "")[:160],
            "command": (str(command)[:300] if command else ""),
            "args_bytes": len(json.dumps(args, default=str)) if args else 0,
        })
    return rows, dropped


def scan_deep(root: Path) -> DeepData:
    """One pass over every session. Read-only; safe to re-run."""
    started = datetime.now()
    root = Path(root)
    warnings: list[str] = []
    if not root.is_dir():
        raise FileNotFoundError(f"brain directory not found: {root}")

    history = _load_history(root)
    subs = _load_subagent_parents(root)
    current_model = _current_model(root)

    tool_rows: list[dict] = []
    turnaround_rows: list[dict] = []
    gap_rows: list[dict] = []
    failure_rows: list[dict] = []
    denial_rows: list[dict] = []
    command_rows: list[dict] = []
    switch_rows: list[dict] = []
    meta_rows: list[dict] = []
    artifact_rows: list[dict] = []
    message_rows: list[dict] = []

    counters: Counter = Counter()
    step_days: dict[str, Counter] = defaultdict(Counter)
    capped_gaps = 0

    for sdir in sorted(root.iterdir()):
        if not sdir.is_dir():
            continue
        tf = _transcript(sdir)
        if tf is None:
            continue
        sid = sdir.name

        steps: list[tuple] = []          # (ts, source, is_user, has_tools)
        step_tools: dict[int, list[str]] = defaultdict(list)
        pending_cmds: list[str] = []
        sess = defaultdict(int)

        with tf.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"created_at"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = _parse_ts(o.get("created_at"))
                source = o.get("source") or ""
                status = (o.get("status") or "").upper()
                stype = (o.get("type") or "").upper()
                content = o.get("content") or ""
                day = ts.astimezone().date().isoformat() if ts else None
                idx = o.get("step_index")
                is_user = stype == "USER_INPUT" or source.startswith("USER")

                steps.append((ts, source, is_user, idx))

                if day:
                    drow = step_days[day]
                    drow["steps"] += 1
                    if o.get("thinking"):
                        drow["thinking_steps"] += 1
                    if isinstance(o.get("input_tokens"), int):
                        drow["model_calls"] += 1
                        if not o.get("cache_read_tokens"):
                            drow["cache_miss_calls"] += 1
                    if stype == "CHECKPOINT":
                        drow["checkpoints"] += 1

                if o.get("thinking"):
                    sess["thinking_steps"] += 1
                if isinstance(o.get("input_tokens"), int):
                    sess["model_calls"] += 1
                    if not o.get("cache_read_tokens"):
                        sess["cache_miss_calls"] += 1
                    if not ts:
                        counters["token_steps_without_timestamp"] += 1
                if stype == "CHECKPOINT":
                    sess["checkpoints"] += 1
                if not ts:
                    continue

                # --- failures -------------------------------------------------
                if status in ("ERROR", "INVALID", "FAILED") or stype == "ERROR_MESSAGE":
                    failure_rows.append({
                        "date": day, "session_id": sid, "status": status or stype,
                        "text": _failure_text(content, status), "has_content": bool(content),
                    })

                # --- approval denials ----------------------------------------
                if content and _DENIAL_RE.search(content):
                    stamps = _TS_RE.findall(content)
                    wait = None
                    if len(stamps) >= 2:
                        a, b = _parse_ts(stamps[0]), _parse_ts(stamps[-1])
                        if a and b:
                            wait = max((b - a).total_seconds(), 0.0)
                    denial_rows.append({
                        "date": day, "session_id": sid,
                        # the command this denial answers was issued by the previous step
                        "command": (pending_cmds[0] if pending_cmds else "")[:200],
                        "wait_seconds": wait,
                        "text": " ".join(content.split())[:200],
                    })
                    pending_cmds = []  # consumed: it must not also be billed as an executed command
                    counters["denials_in_content"] += 1

                # --- model switches ------------------------------------------
                for frm, to in _SETTING_SWITCH_RE.findall(content):
                    switch_rows.append({"date": day, "session_id": sid,
                                        "from_model": _clean_model_name(frm),
                                        "to_model": _clean_model_name(to)})

                # --- tool calls ----------------------------------------------
                tool_batch, dropped = _tool_rows(o, sid, day, idx)
                counters["corrupted_tool_names_dropped"] += dropped
                for row in tool_batch:
                    row["status"] = status
                    tool_rows.append(row)
                    step_tools[idx].append(row["tool"])
                    counters[f"tool:{row['tool']}"] += 1
                    if row["server"]:
                        counters[f"mcp:{row['server']}"] += 1
                    if row["tool"] == "schedule":
                        counters["schedule_calls"] += 1

                # --- command execution time + exit code (CLI's own stamps) ----
                # Only the step immediately after the run_command call can be that
                # command's result: pairing any later "Created/Completed" block with
                # an older command is how you report 18-hour "commands".
                has_run_command = any(r["tool"] == "run_command" for r in tool_batch)
                if has_run_command:
                    pending_cmds = [r["command"] for r in tool_batch if r["command"]]
                elif pending_cmds:
                    duration, exit_code, note = _command_result(content)
                    if duration is not None or note:
                        command_rows.append({
                            "date": day, "session_id": sid, "command": pending_cmds[0],
                            "duration_seconds": duration, "exit_code": exit_code,
                            "note": note, "source": "command stamps",
                        })
                    pending_cmds = []

        # --- gaps: busy (MODEL->MODEL) and idle (->USER) ----------------------
        for (t0, s0, _u0, _i0), (t1, s1, u1, _i1) in zip(steps, steps[1:]):
            if not t0 or not t1:
                continue
            raw = (t1 - t0).total_seconds()
            if raw < 0:
                continue
            if raw > GAP_CAP_SECONDS:
                capped_gaps += 1
                raw = GAP_CAP_SECONDS  # capped, not dropped: see the warning below
            if s0 == "MODEL" and s1 == "MODEL":
                kind = "busy"
            elif u1:
                kind = "idle"
            else:
                kind = "other"
            gap_rows.append({"date": t1.astimezone().date().isoformat(), "session_id": sid,
                             "kind": kind, "seconds": raw})

        # --- tool turnaround: call -> next recorded step ----------------------
        # Keyed by the step's own step_index: positions and step_index drift apart
        # on sessions that start numbering elsewhere, and then nothing matches.
        for i, (t0, s0, _u0, step_index) in enumerate(steps[:-1]):
            if s0 != "MODEL" or not t0:
                continue
            tools = step_tools.get(step_index)
            if not tools:
                continue
            t1 = steps[i + 1][0]
            if not t1:
                continue
            seconds = (t1 - t0).total_seconds()
            if seconds < 0 or seconds > GAP_CAP_SECONDS:
                continue
            for tool in tools:
                turnaround_rows.append({"tool": tool, "seconds": seconds,
                                        "date": t0.astimezone().date().isoformat()})

        # --- tool output volume ----------------------------------------------
        out_bytes = 0
        biggest = 0
        steps_dir = sdir / ".system_generated" / "steps"
        if steps_dir.is_dir():
            for sub in steps_dir.iterdir():
                f = sub / "output.txt"
                try:
                    if f.is_file():
                        size = f.stat().st_size
                        out_bytes += size
                        biggest = max(biggest, size)
                        sess["tool_outputs"] += 1
                except OSError:
                    continue
        sess["tool_output_bytes"] = out_bytes
        sess["biggest_tool_output_bytes"] = biggest

        # --- workspace + identity --------------------------------------------
        parent = subs.get(sid, (None, None))[1]
        workspace = history.get(sid)
        kind = "subagent" if sid in subs else ("main" if sid in history else "other")
        if workspace is None and parent:
            workspace = history.get(parent, "(subagent: parent workspace unknown)")
        timestamps = [t for t, *_ in steps if t]
        first = min(timestamps) if timestamps else None
        last = max(timestamps) if timestamps else None
        meta_rows.append({
            "session_id": sid,
            "kind": kind,
            "workspace": workspace or "(unattributed)",
            "project": _project_name(workspace) if workspace else "(unattributed)",
            "parent": parent or "",
            "first_utc": first,
            "last_utc": last,
            "wall_seconds": (last - first).total_seconds() if first and last else 0.0,
            "steps": len(steps),
            "model_calls": sess["model_calls"],
            "cache_miss_calls": sess["cache_miss_calls"],
            "thinking_steps": sess["thinking_steps"],
            "checkpoints": sess["checkpoints"],
            "tool_outputs": sess["tool_outputs"],
            "tool_output_bytes": sess["tool_output_bytes"],
            "biggest_tool_output_bytes": sess["biggest_tool_output_bytes"],
        })

        # --- artifacts (session root *.md.metadata.json) ----------------------
        for f in sdir.glob("*.metadata.json"):
            try:
                m = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue
            artifact_rows.append({
                "session_id": sid, "name": f.name.replace(".metadata.json", ""),
                "summary": str(m.get("summary") or "")[:200],
                "updated_at": m.get("updatedAt"),
                "request_feedback": bool(m.get("requestFeedback")),
                "user_facing": bool(m.get("userFacing", True)),
            })

        # --- inter-agent messages (count all, parse the newest few) -----------
        msg_dir = sdir / ".system_generated" / "messages"
        if msg_dir.is_dir():
            files = [f for f in msg_dir.glob("*.json") if f.is_file() and f.name != "read.json"]
            counters["messages_total"] += len(files)
            if files:
                receipts = _read_receipts(msg_dir / "read.json")
                counters["messages_read"] += sum(1 for v in receipts.values() if v)
                newest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:5]
                for f in newest:
                    try:
                        m = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                    except (json.JSONDecodeError, OSError):
                        continue
                    render = m.get("renderDetails") or {}
                    message_rows.append({
                        "session_id": sid,
                        "sender": str(m.get("sender") or "").split("/")[-1][:40],
                        "title": str(render.get("messageTitle") or "")[:120],
                        "priority": str(m.get("priority") or "").replace("MESSAGE_PRIORITY_", ""),
                        "timestamp": m.get("timestamp"),
                        "read": bool(receipts.get(str(m.get("id")), False)),
                    })

    counters["task_logs"] = sum(1 for _ in root.glob("*/.system_generated/tasks/task-*.log"))
    counters["checkpoints"] = sum(int(r["checkpoints"]) for r in meta_rows)
    counters["tool_outputs"] = sum(int(r["tool_outputs"]) for r in meta_rows)
    counters["tool_output_bytes"] = sum(int(r["tool_output_bytes"]) for r in meta_rows)
    counters["steps"] = sum(int(r["steps"]) for r in meta_rows)
    counters["thinking_steps"] = sum(int(r["thinking_steps"]) for r in meta_rows)
    counters["model_calls"] = sum(int(r["model_calls"]) for r in meta_rows)
    counters["cache_miss_calls"] = sum(int(r["cache_miss_calls"]) for r in meta_rows)
    counters["sessions_scanned"] = len(meta_rows)
    counters["capped_gaps"] = capped_gaps
    counters["artifact_metadata_files"] = len(artifact_rows)
    counters["subagent_dispatches"] = sum(
        1 for r in tool_rows if r["tool"] in ("invoke_subagent", "invoke_subagents"))

    if capped_gaps:
        warnings.append(
            f"{capped_gaps} gap(s) longer than {GAP_CAP_SECONDS // 3600} h were capped at "
            f"{GAP_CAP_SECONDS // 3600} h for the time budget: an overnight gap is not work, but it is "
            "also not zero, so the budget is an approximation, not a stopwatch.")

    elapsed = (datetime.now() - started).total_seconds()
    return DeepData(
        scanned_at=datetime.now().astimezone(), root=str(root), duration_seconds=elapsed,
        tool_calls=_frame(tool_rows, ["session_id", "date", "step_index", "tool", "server",
                                      "action", "command", "args_bytes", "status"]),
        turnarounds=_frame(turnaround_rows, ["tool", "seconds", "date"]),
        gaps=_frame(gap_rows, ["date", "session_id", "kind", "seconds"]),
        failures=_frame(failure_rows, ["date", "session_id", "status", "text", "has_content"]),
        denials=_frame(denial_rows, ["date", "session_id", "command", "wait_seconds", "text"]),
        commands=_frame(command_rows, ["date", "session_id", "command", "duration_seconds",
                                       "exit_code", "note", "source"]),
        model_switches=_frame(switch_rows, ["date", "session_id", "from_model", "to_model"]),
        session_meta=_frame(meta_rows, ["session_id", "kind", "workspace", "project", "parent",
                                        "first_utc", "last_utc", "wall_seconds", "steps",
                                        "model_calls", "cache_miss_calls", "thinking_steps",
                                        "checkpoints", "tool_outputs", "tool_output_bytes",
                                        "biggest_tool_output_bytes"]),
        step_days=pd.DataFrame(
            [{"date": pd.Timestamp(d), **v} for d, v in sorted(step_days.items())],
            columns=["date", "steps", "model_calls", "cache_miss_calls", "thinking_steps",
                     "checkpoints"],
        ).sort_values("date").reset_index(drop=True) if step_days else _empty(
            ["date", "steps", "model_calls", "cache_miss_calls", "thinking_steps", "checkpoints"]),
        artifacts=_frame(artifact_rows, ["session_id", "name", "summary", "updated_at",
                                         "request_feedback", "user_facing"]),
        messages=_frame(message_rows, ["session_id", "sender", "title", "priority",
                                       "timestamp", "read"]),
        counters=dict(counters),
        warnings=warnings + ([f"current model per settings.json: {current_model}"] if current_model else []),
    )


def _frame(rows: list[dict], cols: list[str]) -> pd.DataFrame:
    if not rows:
        return _empty(cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


# --- derived views -------------------------------------------------------
def gaps_daily(gaps: pd.DataFrame) -> pd.DataFrame:
    """Per-day busy vs idle hours (gap-capped, so an approximation)."""
    if gaps is None or gaps.empty:
        return pd.DataFrame(columns=["date", "busy_hours", "idle_hours", "other_hours"])
    d = gaps.copy()
    d["date"] = pd.to_datetime(d["date"])
    pivot = d.pivot_table(index="date", columns="kind", values="seconds", aggfunc="sum").fillna(0)
    for k in ("busy", "idle", "other"):
        if k not in pivot:
            pivot[k] = 0.0
    out = (pivot[["busy", "idle", "other"]] / 3600.0).reset_index()
    return out.rename(columns={"busy": "busy_hours", "idle": "idle_hours", "other": "other_hours"})


def turnaround_stats(turnarounds: pd.DataFrame) -> pd.DataFrame:
    """Median/p90 turnaround per tool. Seconds, second-resolution timestamps."""
    if turnarounds is None or turnarounds.empty:
        return pd.DataFrame(columns=["tool", "calls", "p50_seconds", "p90_seconds", "total_minutes"])
    g = turnarounds.groupby("tool")["seconds"]
    out = pd.DataFrame({
        "calls": g.size(),
        "p50_seconds": g.median(),
        "p90_seconds": g.quantile(0.9),
        "total_minutes": g.sum() / 60.0,
    }).reset_index()
    return out.sort_values("total_minutes", ascending=False).reset_index(drop=True)


def failure_summary(failures: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Most common failure strings - the fixable ones repeat."""
    if failures is None or failures.empty:
        return pd.DataFrame(columns=["text", "count", "last_seen"])
    g = failures.groupby("text")
    out = pd.DataFrame({
        "count": g.size(),
        "last_seen": g["date"].max(),
        "sessions": g["session_id"].nunique(),
    }).reset_index().sort_values("count", ascending=False).head(top)
    return out.reset_index(drop=True)


def workspace_totals(sessions: pd.DataFrame, meta: pd.DataFrame, prices) -> pd.DataFrame:
    """Join token totals to workspace. Cost is computed, never read."""
    if sessions is None or sessions.empty or meta is None or meta.empty:
        return pd.DataFrame(columns=["project", "workspace", "sessions", "calls", "tokens",
                                     "fresh_in", "cached", "output", "cost_usd", "cost_per_mtok_usd"])
    from . import metrics

    merged = sessions.merge(meta[["session_id", "workspace", "project"]], on="session_id", how="left")
    merged["workspace"] = merged["workspace"].fillna("(unattributed)")
    merged["project"] = merged["project"].fillna("(unknown)")
    rows = []
    for (project, workspace), g in merged.groupby(["project", "workspace"], dropna=False):
        fresh = int(g["fresh_in"].sum())
        cached = int(g["cached"].sum())
        out = int(g["output"].sum())
        cost = metrics.api_cost_usd(fresh, cached, out, prices)
        rows.append({
            "project": project, "workspace": workspace, "sessions": int(len(g)),
            "calls": int(g["calls"].sum()), "fresh_in": fresh, "cached": cached, "output": out,
            "tokens": fresh + cached + out, "cost_usd": cost,
            "cost_per_mtok_usd": metrics.blended_rate_usd_per_mtok(cost, fresh + cached + out),
        })
    return pd.DataFrame(rows).sort_values("cost_usd", ascending=False).reset_index(drop=True)


def unit_economics(overview, ticks: dict) -> dict:
    """$ per call / per session / per agent-busy-hour, using measured denominators."""
    calls = overview.totals.calls
    sessions = overview.totals.sessions
    busy_hours = float(ticks.get("busy_hours") or 0.0)
    from . import metrics
    return {
        "cost_per_call_usd": metrics.safe_div(overview.api_cost_usd, calls),
        "cost_per_session_usd": metrics.safe_div(overview.api_cost_usd, sessions),
        "cost_per_busy_hour_usd": metrics.safe_div(overview.api_cost_usd, busy_hours),
        "tokens_per_call": metrics.safe_div(overview.totals.total, calls),
        "calls_per_busy_hour": metrics.safe_div(calls, busy_hours),
        "busy_hours": busy_hours,
    }


def waste_estimate(overview, failure_count: int) -> dict:
    """Tokens spent on calls that ended in a failed or invalid step.

    A crude proxy: failures are matched to model calls 1:1 and charged the
    average observed cost per call. It is an order-of-magnitude figure, not an
    accounting number, and the UI must say so.
    """
    from . import metrics
    calls = max(int(overview.totals.calls), 1)
    share = min(failure_count / calls, 1.0)
    return {
        "failure_count": int(failure_count),
        "share_of_calls": share,
        "tokens_at_risk": overview.totals.total * share,
        "cost_usd": overview.api_cost_usd * share,
        "method": "failures x average observed cost per call (order of magnitude only)",
    }
