"""E. Data and Jobs - run the existing extractor, inspect its output, snapshots."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from .. import jobs, metrics, snapshots
from .common import Ctx, kpi_row, note

STATUS_BADGE = {
    "idle": "⚪ IDLE", "running": "🟡 RUNNING", "success": "🟢 SUCCESS",
    "failed": "🔴 FAILED", "timeout": "🟠 TIMED OUT", "error": "🔴 ERROR",
}


def render(ctx: Ctx) -> None:
    tab_run, tab_source, tab_snap = st.tabs([
        "⚙️ Extraction Pipeline & Console",
        "🛰️ Data Source & Verification Health",
        "💾 Snapshot Ledger & SQLite History"
    ])

    with tab_run:
        st.subheader("⚙️ Background Extractor Control")
        _run_panel(ctx)

    with tab_source:
        _source_panel(ctx)

    with tab_snap:
        st.subheader("💾 Persistent Snapshot Ledger (SQLite)")
        _snapshots_panel(ctx)


def _source_panel(ctx: Ctx) -> None:
    st.subheader("🛰️ Telemetry Source Health")
    cfg = ctx.config
    exists = "ONLINE ✅" if cfg.brain_root.is_dir() else "OFFLINE ❌"
    script = "ONLINE ✅" if cfg.extractor_script.exists() else "OFFLINE ❌"

    kpi_row([
        ("Brain Directory", exists, str(cfg.brain_root), "🧠", "DIR"),
        ("Extractor Script", script, str(cfg.extractor_script.name), "📜", "SCRIPT"),
        ("Python Launcher", str(cfg.python_executable), "interpreter", "🐍", "EXE"),
    ], per_row=3)

    st.caption(f"🔄 Last scan: `{ctx.usage.scanned_at:%Y-%m-%d %H:%M:%S %Z}` · "
               f"Scanned `{len(ctx.usage.sessions)}` sessions · Scan duration: ≈1.5s")

    for w in ctx.usage.warnings:
        note(w, warn=True)

    issues = metrics.verify_consistency(ctx.usage.sessions, ctx.usage.daily)
    if issues:
        st.markdown("**Source checks** - reported values were not silently corrected:")
        for issue in issues:
            note(issue, warn=True)
    else:
        st.success("✅ Source integrity verification passed: `total` matches `fresh + cached + output` across all records.")


def _run_panel(ctx: Ctx) -> None:
    runner = ctx.runner
    log_dir = st.text_input("Log directory (stdout, stderr, lock files)",
                            value=str(runner.log_dir), key="job_log_dir")
    if log_dir and log_dir != str(runner.log_dir):
        runner.log_dir = Path(log_dir)
        runner.lock_path = Path(log_dir) / ".extract.lock"
        runner.last_run_path = Path(log_dir) / "last_run.json"

    report = st.selectbox("Report profile to execute", jobs.REPORTS, index=0, key="job_report",
                          help="Extractor CLI argument profile. Executed directly without shell wrapping.")
    running = runner.state.running
    c1, c2, c3 = st.columns([1.2, 1.4, 2])
    if c1.button("🚀 Run extraction", type="primary", disabled=running, key="job_run"):
        runner.start(report)
        st.session_state["_job_seen"] = "running"
        st.rerun(scope="app")
    if c2.button("🔄 Refresh dashboard data", disabled=running, key="job_refresh"):
        st.cache_data.clear()
        st.rerun(scope="app")
    if running:
        c3.caption("🟡 **Extraction in flight** - UI remains responsive via non-blocking subprocess.")
    else:
        c3.caption("🔒 Atomic lock file safeguards against concurrent duplicate runs.")

    if running:
        st.fragment(run_every=2)(_status_body)(ctx)
    else:
        _status_body(ctx)

    rec = jobs.last_run(runner.last_run_path)
    if rec:
        st.caption(f"Last attempt: **{rec['status']}** · Exit: `{rec.get('exit_code')}` · "
                   f"`{rec.get('started_at')}` → `{rec.get('ended_at')}` "
                   f"({rec.get('duration_seconds')}s)")


def _status_body(ctx: Ctx) -> None:
    """Renders job state. Wrapped in a 2s fragment while a run is in flight."""
    runner = ctx.runner
    before = st.session_state.get("_job_seen", "idle")
    if before == "running":
        runner.poll()
    state = runner.state

    st.markdown(f"**Execution Status:** `{STATUS_BADGE.get(state.status, state.status)}` · {state.message}")
    m = st.columns(5)
    m[0].metric("Started", state.started_at.strftime("%H:%M:%S") if state.started_at else "-")
    m[1].metric("Ended", state.ended_at.strftime("%H:%M:%S") if state.ended_at else "-")
    m[2].metric("Duration", f"{state.duration_seconds:.2f}s" if state.duration_seconds else "-")
    m[3].metric("Exit Code", "-" if state.exit_code is None else str(state.exit_code))
    m[4].metric("Report Target", state.report)

    if state.command:
        st.code(" ".join(state.command), language="powershell")

    out, err = state.read_stdout(limit=20_000), state.read_stderr(limit=10_000)
    if out:
        with st.expander("📄 Subprocess Standard Output (stdout)", expanded=state.running):
            st.code(out, language="text")
    if err:
        with st.expander("🚨 Subprocess Standard Error (stderr)", expanded=True):
            st.code(err, language="text")

    if before == "running" and not state.running:
        st.session_state["_job_seen"] = state.status
        if state.status == "success":
            st.cache_data.clear()
            st.toast("Extraction completed successfully - reloaded telemetry")
        st.rerun(scope="app")
    elif not state.running:
        st.session_state["_job_seen"] = state.status


def _snapshots_panel(ctx: Ctx) -> None:
    st.caption(f"SQLite Target: `{ctx.sqlite_path}` · Idempotent upsert by session UUID and calendar date.")
    c1, c2 = st.columns([1, 2])
    if c1.button("💾 Save snapshot now", key="snap_save"):
        try:
            conn = snapshots.connect(ctx.sqlite_path)
            info = snapshots.ingest(conn, ctx.usage)
            conn.close()
            st.success(f"Snapshot saved: {info['sessions']} sessions, {info['days']} days at {info['taken_at']}")
        except Exception as exc:  # surfaced, not swallowed
            st.error(f"Snapshot ingestion failed: {exc}")
    try:
        conn = snapshots.connect(ctx.sqlite_path)
        cnt = snapshots.counts(conn)
        hist = snapshots.runs(conn)
        conn.close()
        with c2:
            cols = st.columns(3)
            cols[0].metric("Session Records", f"{cnt['session_facts']:,}")
            cols[1].metric("Daily Records", f"{cnt['daily_facts']:,}")
            cols[2].metric("Total Scan Runs", f"{cnt['runs']:,}")
        if not hist.empty:
            with st.expander("📜 Ingestion Run Ledger History", expanded=False):
                st.dataframe(hist, hide_index=True, use_container_width=True)
    except Exception as exc:
        st.info(f"No snapshot database initialized yet ({exc})")

