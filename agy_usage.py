#!/usr/bin/env python3
"""Antigravity CLI token usage analyzer (input / output / cached per day and per session).

Scans <brain>/<conversationId>/.system_generated/logs/transcript.jsonl
(default brain dir: ~/.gemini/antigravity-cli/brain).

usage:
  py agy_usage.py [all|daily|sessions|tips] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                  [--top N] [--root PATH] [--in-price X --cache-price X --out-price X]

Costs default to Gemini 3.8 Flash standard-paid rates (USD per 1M tokens, intro
price through 2026-12-31): 0.75 in / 0.075 cached / 3.75 out. Override the
--*-price flags for other models (e.g. Gemini 4 Argon: 2.00/0.10/10.00).
Print mode output and context-cache storage are not included.

Token fields are per model call. input_tokens is FRESH (non-cached) input,
cache_read_tokens is the cached part of the prompt, output_tokens includes
thinking. Total = fresh + cached + output. Subagent conversations have their
own brain dirs and are counted once, labeled "[agent] role (parent ...)".
"""

import argparse, json, os, sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".gemini" / "antigravity-cli" / "brain"

# Gemini 3.8 Flash standard paid tier, USD per 1M tokens (intro price through 2026-12-31):
# input $0.75, cached read $0.075, output $3.75 (incl. thinking).
PRICES = {"in": 0.75, "cache": 0.075, "out": 3.75}


def cost_usd(in_t, cache_t, out_t):
    return (in_t * PRICES["in"] + cache_t * PRICES["cache"] + out_t * PRICES["out"]) / 1e6


def usd(x):
    return f"${x:,.2f}"



def human(n):
    if n < 1000:
        return str(int(n))
    if n < 1_000_000:
        return f"{n / 1e3:.1f}K"
    return f"{n / 1e6:.1f}M"


def parse_ts(s):
    try:
        return datetime.fromisoformat(s)  # 3.11+ handles 'Z'
    except (ValueError, TypeError):
        return None


def load_labels(root):
    """conversationId -> label for main sessions (first prompt in history.jsonl)."""
    labels = {}
    hist = root.parent / "history.jsonl"
    if not hist.exists():
        return labels
    with hist.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = o.get("conversationId")
            if cid and cid not in labels:
                labels[cid] = " ".join(str(o.get("display", "")).split())[:60]
    return labels


def load_subagents(root):
    """conversationId -> (agent, role, parent_id) from each session's subagents/*.json."""
    subs = {}
    for parent in root.iterdir():
        d = parent / ".system_generated" / "subagents"
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            try:
                o = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue
            desc = o.get("subagentDescriptor") or {}
            cid = o.get("conversationId")
            if cid:
                subs[cid] = (desc.get("typeName", "subagent"), desc.get("role", ""), parent.name)
    return subs


def scan(root):
    """session_id -> per-session aggregates, plus raw (local_date, session_id, in, cache, out) rows."""
    labels = load_labels(root)
    subs = load_subagents(root)
    sessions = {}
    daily = defaultdict(lambda: {"steps": 0, "in": 0, "cache": 0, "out": 0, "sessions": set()})
    for sdir in sorted(root.iterdir()):
        if not sdir.is_dir():
            continue
        logs = sdir / ".system_generated" / "logs"
        tf = logs / "transcript.jsonl"
        if not tf.exists():
            tf = logs / "transcript_full.jsonl"  # fallback; same token fields
        if not tf.exists():
            continue
        s = {"steps": 0, "in": 0, "cache": 0, "out": 0, "first": None, "last": None}
        for line in tf.open(encoding="utf-8", errors="replace"):
            if '"input_tokens"' not in line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(o.get("input_tokens"), int):
                continue
            ts = parse_ts(o.get("created_at"))
            s["steps"] += 1
            s["in"] += o["input_tokens"]
            s["cache"] += o.get("cache_read_tokens") or 0
            s["out"] += o.get("output_tokens") or 0
            if ts:
                s["first"] = ts if s["first"] is None else min(s["first"], ts)
                s["last"] = ts if s["last"] is None else max(s["last"], ts)
                day = ts.astimezone().date().isoformat()
                d = daily[day]
                d["steps"] += 1
                d["in"] += o["input_tokens"]
                d["cache"] += o.get("cache_read_tokens") or 0
                d["out"] += o.get("output_tokens") or 0
                d["sessions"].add(sdir.name)
        if not s["steps"]:
            continue
        cid = sdir.name
        s["total"] = s["in"] + s["cache"] + s["out"]
        if cid in subs:
            agent, role, parent = subs[cid]
            s["kind"] = "subagent"
            s["label"] = f"[{agent}] {role} (parent {parent[:8]})"
        elif cid in labels:
            s["kind"] = "main"
            s["label"] = labels[cid] or "(no prompt recorded)"
        else:
            s["kind"] = "other"
            s["label"] = "(not in history.jsonl)"
        sessions[cid] = s
    return sessions, daily


def fmt_date(d):
    return date.fromisoformat(d).strftime("%a %Y-%m-%d")


def report_daily(daily, since, until):
    rows = [(d, v) for d, v in sorted(daily.items()) if (not since or d >= since) and (not until or d <= until)]
    if not rows:
        print("no data in range")
        return
    print(f"{'date':<16}{'sessions':>9}{'calls':>7}{'fresh in':>11}{'cached':>11}{'output':>9}{'total':>11}{'cost':>9}")
    t = {"in": 0, "cache": 0, "out": 0, "steps": 0, "sessions": set()}
    for d, v in rows:
        print(f"{fmt_date(d):<16}{len(v['sessions']):>9}{v['steps']:>7}{human(v['in']):>11}"
              f"{human(v['cache']):>11}{human(v['out']):>9}{human(v['in'] + v['cache'] + v['out']):>11}"
              f"{usd(cost_usd(v['in'], v['cache'], v['out'])):>9}")
        t["in"] += v["in"]; t["cache"] += v["cache"]; t["out"] += v["out"]
        t["steps"] += v["steps"]; t["sessions"] |= v["sessions"]
    print(f"{'TOTAL':<16}{len(t['sessions']):>9}{t['steps']:>7}{human(t['in']):>11}"
          f"{human(t['cache']):>11}{human(t['out']):>9}{human(t['in'] + t['cache'] + t['out']):>11}"
          f"{usd(cost_usd(t['in'], t['cache'], t['out'])):>9}")


def report_sessions(sessions, since, until, top):
    rows = []
    for cid, s in sessions.items():
        if s["first"]:
            d = s["first"].astimezone().date().isoformat()
            if (since and d < since) or (until and d > until):
                continue
        rows.append((cid, s))
    rows.sort(key=lambda kv: kv[1]["total"], reverse=True)
    grand = sum(s["total"] for _, s in rows) or 1
    if top and len(rows) > top:
        shown = rows[:top]
        print(f"top {top} of {len(rows)} sessions (showing {100 * sum(s['total'] for _, s in shown) / grand:.0f}% of tokens)")
    else:
        shown = rows
    print(f"{'cost':>8}{'total':>9}{'fresh in':>10}{'cached':>10}{'output':>8}{'calls':>7}  {'started':<16}session")
    for cid, s in shown:
        when = s["first"].astimezone().strftime("%Y-%m-%d %H:%M") if s["first"] else "?"
        print(f"{usd(cost_usd(s['in'], s['cache'], s['out'])):>8}{human(s['total']):>9}{human(s['in']):>10}{human(s['cache']):>10}{human(s['out']):>8}"
              f"{s['steps']:>7}  {when:<16}{s['label']}  {cid[:8]}")


def report_tips(sessions, daily):
    tot = {"in": 0, "cache": 0, "out": 0, "steps": 0}
    for s in sessions.values():
        for k in tot:
            tot[k] += s[k]
    if not tot["steps"]:
        print("no data")
        return
    prompt = tot["in"] + tot["cache"]
    hit = 100 * tot["cache"] / prompt if prompt else 0
    print("== numbers ==")
    print(f"model calls        : {tot['steps']}")
    print(f"fresh input        : {human(tot['in'])}  ({100 * tot['in'] / prompt:.0f}% of prompt, billed full price)")
    print(f"cached input       : {human(tot['cache'])}  ({hit:.0f}% cache hit rate, billed at a discount)")
    print(f"output (incl. thinking): {human(tot['out'])}")
    print(f"estimated cost     : {usd(cost_usd(tot['in'], tot['cache'], tot['out']))} at "
          f"${PRICES['in']}/{PRICES['cache']}/{PRICES['out']} per 1M in/cache/out tokens")
    active_days = len({d for d, v in daily.items() if v["steps"]})
    print(f"active days        : {active_days}; sessions/day: {len(sessions) / max(active_days, 1):.1f}")

    print("\n== levers, ordered by your data ==")

    # 1. long-context sessions: cached tokens are still tokens
    big = sorted(sessions.items(), key=lambda kv: kv[1]["cache"], reverse=True)[:3]
    share = 100 * sum(s["cache"] for _, s in big) / max(tot["cache"], 1)
    b = big[0][1]
    c_in = cost_usd(tot["in"], 0, 0)
    c_cache = cost_usd(0, tot["cache"], 0)
    c_out = cost_usd(0, 0, tot["out"])
    c_all = c_in + c_cache + c_out
    print(f"- Cost split: fresh input {usd(c_in)} ({100 * c_in / c_all:.0f}%), cached {usd(c_cache)}"
          f" ({100 * c_cache / c_all:.0f}%), output {usd(c_out)} ({100 * c_out / c_all:.0f}%).")
    print(f"- Cached reads are your biggest token volume ({human(tot['cache'])} total) though billed at 1/10th;")
    print(f"  {share:.0f}% of it is in the worst 3 sessions. Worst: '{b['label'][:50]}' averaged")
    print(f"  {human(b['cache'] / max(b['steps'], 1))} cached tokens per call over {b['steps']} calls. Every call re-sends the")
    print(f"  whole conversation. Fix: one session per task, /clear or a new session between tasks.")

    # 2. fresh input heavy = big files / rebuilt cache
    freshy = [(cid, s) for cid, s in sessions.items() if s["in"] / max(s["steps"], 1) > 8000 and s["steps"] >= 20]
    if freshy:
        freshy.sort(key=lambda kv: kv[1]["in"], reverse=True)
        cid, s = freshy[0]
        print(f"- {len(freshy)} sessions average >8K fresh input per call "
              f"(worst: {human(s['in'] / s['steps'])}/call).")
        print("  That is large file contents entering context repeatedly. Fix: graph-first exploration,")
        print("  delegate reads to a researcher subagent, read targeted line ranges instead of whole files.")
    if hit < 70:
        print(f"- Cache hit rate is {hit:.0f}%. Edits early in a long conversation invalidate the cache,")
        print("  so later calls re-process fresh input. Batching edits/critique rounds instead of many small")
        print("  interleaved ones keeps the cached prefix stable.")

    # 3. output
    if tot["out"] < 0.02 * prompt:
        print(f"- Output is small ({human(tot['out'])}); the cost is context management, not generation.")
    else:
        print(f"- Output incl. thinking is {human(tot['out'])} ({100 * tot['out'] / (prompt + tot['out']):.0f}% of all tokens);")
        print("  verbose agent prompts/thinking add up, but context still dominates.")

    print("\n== checklist (from the 2026-10-15 efficiency review) ==")
    print("- start a new session per task; long sessions are what produce the M-token cached columns")
    print("- keep plan-critic rounds scoped to changed sections (already fixed in planner.md/plan-critic.md)")
    print("- prefer the code-review-graph tools + researcher subagent over reading whole files")
    print("- watch for re-dispatch loops (premature COMPLETED race) - a duplicated task doubles its tokens")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", nargs="?", default="all", choices=["all", "daily", "sessions", "tips"])
    ap.add_argument("--since", help="YYYY-MM-DD (local, inclusive)")
    ap.add_argument("--until", help="YYYY-MM-DD (local, inclusive)")
    ap.add_argument("--top", type=int, default=25, help="max sessions to show (0 = all)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="brain dir")
    ap.add_argument("--in-price", type=float, default=PRICES["in"], help="USD per 1M fresh input tokens")
    ap.add_argument("--cache-price", type=float, default=PRICES["cache"], help="USD per 1M cached-read tokens")
    ap.add_argument("--out-price", type=float, default=PRICES["out"], help="USD per 1M output tokens")
    args = ap.parse_args()
    PRICES["in"], PRICES["cache"], PRICES["out"] = args.in_price, args.cache_price, args.out_price

    root = Path(os.path.expanduser(args.root))
    if not root.is_dir():
        sys.exit(f"not found: {root}")

    sessions, daily = scan(root)

    if args.report in ("all", "daily"):
        print("== tokens per day ==")
        report_daily(daily, args.since, args.until)
        print()
    if args.report in ("all", "sessions"):
        print("== tokens per session ==")
        report_sessions(sessions, args.since, args.until, args.top)
        print()
    if args.report in ("all", "tips"):
        report_tips(sessions, daily)


if __name__ == "__main__":
    main()
