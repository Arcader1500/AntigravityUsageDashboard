"""Shared fixtures. The numbers come from the supplied usage summary and the
hand-verified rows in it - they are test data, never the live dataset."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agy_dash.source import UsageData  # noqa: E402
from agy_dash import source  # noqa: E402

# Snapshot aggregate from the handoff doc (section 3).
DOC_SNAPSHOT = {
    "sessions": 127, "calls": 7323,
    "fresh_in": 55_000_000, "cached": 631_600_000, "output": 3_900_000,
    "total": 690_600_000, "cost_usd": 103.42,
}

# Session rows chosen so their sums equal the daily rows below (verify_consistency passes).
_FIXTURE_SESSIONS = [
    # id, label, kind, calls, fresh, cached, out, first_date, last_date
    ("fec70268", "verify the october usage numbers", "main", 41, 396_400, 889_400, 17_700,
     "2026-10-05", "2026-10-05"),
    ("26082efd", "big long-context session", "main", 1174, 6_000_000, 90_000_000, 400_000,
     "2026-10-08", "2026-10-08"),
    ("sub00001", "[code-reviewer] reviewer (parent 26082efd)", "subagent", 220, 4_400_000,
     30_200_000, 180_600, "2026-10-08", "2026-10-08"),
    ("aaaabbbb", "(not in history.jsonl)", "other", 1430, 9_900_000, 105_600_000, 964_800,
     "2026-10-15", "2026-10-15"),
]

_FIXTURE_DAILY = [
    ("2026-10-05", 41, 1, 396_400, 889_400, 17_700),
    ("2026-10-08", 1174, 2, 10_400_000, 120_200_000, 580_600),
    ("2026-10-15", 1430, 1, 9_900_000, 105_600_000, 964_800),
]


@pytest.fixture
def usage() -> UsageData:
    sessions = pd.DataFrame([{
        "session_id": sid, "label": label, "kind": kind, "calls": calls,
        "fresh_in": fresh, "cached": cached, "output": out,
        "total": fresh + cached + out,
        "first_utc": datetime.fromisoformat(first + "T10:00:00+00:00"),
        "last_utc": datetime.fromisoformat(last + "T12:00:00+00:00"),
        "first_date": first, "last_date": last,
    } for sid, label, kind, calls, fresh, cached, out, first, last in _FIXTURE_SESSIONS],
        columns=source.SESSION_COLUMNS)
    daily = pd.DataFrame([{
        "date": pd.Timestamp(d), "calls": calls, "sessions": n,
        "fresh_in": fresh, "cached": cached, "output": out,
        "total": fresh + cached + out,
    } for d, calls, n, fresh, cached, out in _FIXTURE_DAILY], columns=source.DAILY_COLUMNS)
    return UsageData(sessions, daily, datetime.now(timezone.utc).astimezone(), "fixture://brain", [])


@pytest.fixture
def flat_usage(usage) -> UsageData:
    """Same sessions, daily rows flattened to one identical value per day."""
    daily = usage.daily.copy()
    daily["fresh_in"] = 1_000_000
    daily["cached"] = 0
    daily["output"] = 0
    daily["total"] = 1_000_000
    return UsageData(usage.sessions, daily, usage.scanned_at, usage.root, [])


# --- rich synthetic brain (real on-disk layout, for deep-scan + app tests) ---
WORKSPACE = r"C:\Users\atharva.bedekar\PycharmProjects\DemoProject"
MAIN_ID = "aaaa1111-2222-3333-4444-555566667777"
SUB_ID = "bbbb9999-8888-7777-6666-555544443333"
OTHER_ID = "cccc3333-4444-5555-6666-777788889999"


def _model_call(step, ts, *, fresh=1000, cached=5000, out=200, thinking=None, tools=None):
    line = {
        "step_index": step, "source": "MODEL", "type": "PLANNER_RESPONSE" if tools else "GENERIC",
        "status": "DONE", "created_at": ts, "input_tokens": fresh, "cache_read_tokens": cached,
        "output_tokens": out,
    }
    if thinking:
        line["thinking"] = thinking
    if tools:
        line["tool_calls"] = tools
    return line


def _step(step, ts, source, stype, status, content=None, **extra):
    line = {"step_index": step, "source": source, "type": stype, "status": status,
            "created_at": ts}
    if content is not None:
        line["content"] = content
    line.update(extra)
    return line


def build_brain(tmp_path: Path) -> Path:
    """A brain directory exercising every signal the deep scanner reads."""
    import json as _json

    brain = tmp_path / "brain"
    logs = brain / MAIN_ID / ".system_generated" / "logs"
    logs.mkdir(parents=True)

    STAMPS = "Created At: 2026-10-05T10:00:05+00:00\nCompleted At: 2026-10-05T10:00:18+00:00"
    CORRUPT = "invoke_subagent" + (" x" * 200)  # the real logs contain one of these

    steps = [
        _step(1, "2026-10-05T10:00:00+00:00", "USER_EXPLICIT", "USER_INPUT", "DONE",
              "<USER_REQUEST>run the tests</USER_REQUEST>\n<USER_SETTINGS_CHANGE>\nThe user changed "
              "setting `Model Selection` from None to Claude Sonnet. No need to comment on this change.\n"),
        _model_call(2, "2026-10-05T10:00:05+00:00", thinking="let me run pytest", tools=[
            {"name": "run_command", "args": {"CommandLine": "uv run pytest -q", "Cwd": WORKSPACE}},
        ]),
        _step(3, "2026-10-05T10:00:20+00:00", "MODEL", "GENERIC", "DONE",
              f"{STAMPS}\n\nThe command exited with code 1.\nOutput:\n1 failed, 3 passed",
              input_tokens=1200, cache_read_tokens=0, output_tokens=90),   # cache miss
        _model_call(4, "2026-10-05T10:01:00+00:00", thinking="check the file", tools=[
            {"name": "view_file", "args": {"File": "src/app.py"}},
            {"name": "call_mcp_tool", "args": {"ServerName": "context7", "ToolName": "query-docs"}},
            {"name": CORRUPT, "args": {}},
        ]),
        _model_call(5, "2026-10-05T10:01:04+00:00"),
        _step(6, "2026-10-05T10:01:10+00:00", "MODEL", "GENERIC", "INVALID",
              "Encountered error: target content not found in the file; the Target must exactly match."),
        _step(7, "2026-10-05T10:01:40+00:00", "SYSTEM", "ERROR_MESSAGE", "DONE",
              "Created At: 2026-10-05T10:01:10+00:00\nCompleted At: 2026-10-05T10:02:10+00:00\n"
              "permission check failed: the command was denied"),
        _step(8, "2026-10-05T10:01:45+00:00", "SYSTEM", "CHECKPOINT", "DONE", "context truncated"),
        _step(9, "2026-10-05T11:00:00+00:00", "USER_EXPLICIT", "USER_INPUT", "DONE",
              "<USER_REQUEST>continue</USER_REQUEST>"),
        _model_call(10, "2026-10-05T11:00:30+00:00", thinking="delegating", tools=[
            {"name": "invoke_subagent", "args": {"Type": "researcher"}},
            {"name": "search_web", "args": {"Query": "streamlit caching"}},
            {"name": "ask_question", "args": {"Question": "which model?"}},
        ]),
    ]
    (logs / "transcript_full.jsonl").write_text(
        "\n".join(_json.dumps(s) for s in steps) + "\n", encoding="utf-8")

    # tool output volume
    (brain / MAIN_ID / ".system_generated" / "steps" / "1").mkdir(parents=True)
    (brain / MAIN_ID / ".system_generated" / "steps" / "1" / "output.txt").write_text(
        "x" * 2048, encoding="utf-8")

    # subagent session (second day, so token data spans multiple days)
    sub_logs = brain / SUB_ID / ".system_generated" / "logs"
    sub_logs.mkdir(parents=True)
    sub_steps = [
        _model_call(1, "2026-10-06T11:00:40+00:00", fresh=500, cached=2500, out=50),
        _model_call(2, "2026-10-06T11:00:50+00:00", fresh=500, cached=3000, out=60, thinking="hmm"),
    ]
    (sub_logs / "transcript_full.jsonl").write_text(
        "\n".join(_json.dumps(s) for s in sub_steps) + "\n", encoding="utf-8")
    subs = brain / MAIN_ID / ".system_generated" / "subagents"
    subs.mkdir(parents=True)
    (subs / "sub.json").write_text(_json.dumps({
        "conversationId": SUB_ID,
        "subagentDescriptor": {"typeName": "researcher", "role": "fact finder"}}), encoding="utf-8")

    # a third day with no history entry, so it stays "other" kind
    other_logs = brain / OTHER_ID / ".system_generated" / "logs"
    other_logs.mkdir(parents=True)
    other_steps = [
        _model_call(1, "2026-10-07T09:00:00+00:00", fresh=700, cached=1200, out=80),
        _model_call(2, "2026-10-07T09:05:00+00:00", fresh=800, cached=1500, out=90),
    ]
    (other_logs / "transcript_full.jsonl").write_text(
        "\n".join(_json.dumps(s) for s in other_steps) + "\n", encoding="utf-8")

    # inter-agent messages + read receipts
    msg_dir = brain / MAIN_ID / ".system_generated" / "messages"
    msg_dir.mkdir(parents=True)
    (msg_dir / "msg1.json").write_text(_json.dumps({
        "id": "msg-1", "recipient": MAIN_ID, "sender": f"{MAIN_ID}/task-29",
        "priority": "MESSAGE_PRIORITY_HIGH", "timestamp": "2026-10-05T10:00:19Z",
        "renderDetails": {"messageTitle": "Run pytest finished"},
        "content": "Task done"}, ), encoding="utf-8")
    (msg_dir / "read.json").write_text(_json.dumps({"msg-1": True}), encoding="utf-8")

    # artifact metadata at the session root
    (brain / MAIN_ID / "walkthrough.md.metadata.json").write_text(_json.dumps({
        "summary": "Walkthrough of the fix", "updatedAt": "2026-10-05T10:05:00Z",
        "requestFeedback": True, "userFacing": True}), encoding="utf-8")

    # history + settings
    history = [
        {"conversationId": MAIN_ID, "display": "run the tests", "workspace": WORKSPACE,
         "timestamp": 1759660000000, "type": "main"},
    ]
    (brain.parent / "history.jsonl").write_text(
        "\n".join(_json.dumps(h) for h in history) + "\n", encoding="utf-8")
    (brain.parent / "settings.json").write_text(
        _json.dumps({"model": "Claude Sonnet", "agentMode": "accept-edits"}), encoding="utf-8")
    return brain


@pytest.fixture
def rich_brain(tmp_path) -> Path:
    return build_brain(tmp_path)
