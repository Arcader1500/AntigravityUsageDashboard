"""Deep signal extraction: tool truth, gaps, commands, failures, workspaces."""

from __future__ import annotations

import pandas as pd
import pytest

from agy_dash import deep, metrics, pricing
from tests.conftest import MAIN_ID, SUB_ID, WORKSPACE

FLASH = pricing.PriceEntry("gemini-3.8-flash", "Gemini 3.8 Flash", "Google",
                           "2026-10-01", "2026-12-31", 0.75, 0.075, 3.75, verified=True)


@pytest.fixture
def data(rich_brain) -> deep.DeepData:
    return deep.scan_deep(rich_brain)


# --- tool truth -----------------------------------------------------------
def test_tool_calls_come_from_tool_call_names(data):
    assert set(data.tool_calls["tool"]) == {"run_command", "view_file", "call_mcp_tool",
                                            "invoke_subagent", "search_web", "ask_question"}


def test_corrupted_tool_name_is_dropped_not_displayed(data):
    longest = data.tool_calls["tool"].str.len().max()
    assert longest < 40
    assert data.counters["corrupted_tool_names_dropped"] == 1
    assert not data.tool_calls["tool"].str.contains(" ").any()


def test_unknown_tool_name_shaped_like_an_identifier_is_kept(data):
    # filtering is by shape, not by an allowlist that would hide new tools
    assert deep._valid_tool_name("brand_new_tool")
    assert not deep._valid_tool_name("view_file\n\nWait, look at this")
    assert not deep._valid_tool_name("x" * 60)


def test_command_args_are_captured(data):
    cmd = data.tool_calls[data.tool_calls["tool"] == "run_command"].iloc[0]
    assert cmd["command"] == "uv run pytest -q"
    assert data.counters["tool:run_command"] == 1


def test_mcp_server_is_read_from_args(data):
    assert data.counters["mcp:context7"] == 1
    row = data.tool_calls[data.tool_calls["tool"] == "call_mcp_tool"].iloc[0]
    assert row["server"] == "context7"


# --- time budget ----------------------------------------------------------
def test_busy_and_idle_gaps_are_separated(data):
    kinds = set(data.gaps["kind"])
    assert {"busy", "idle", "other"} <= kinds
    busy = data.gaps[data.gaps["kind"] == "busy"]["seconds"]
    assert (busy > 0).all()


def test_gaps_are_capped_at_four_hours(rich_brain, tmp_path):
    # one 30 h gap must be capped, not dropped, and must be reported
    import json
    log = rich_brain / MAIN_ID / ".system_generated" / "logs" / "transcript_full.jsonl"
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    first = json.loads(lines[0])
    first["created_at"] = "2026-10-01T10:00:00+00:00"
    log.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")

    d = deep.scan_deep(rich_brain)
    assert d.counters["capped_gaps"] >= 1
    assert d.gaps["seconds"].max() <= deep.GAP_CAP_SECONDS
    assert any("capped" in w for w in d.warnings)


def test_daily_gap_hours(data):
    g = deep.gaps_daily(data.gaps)
    assert {"busy_hours", "idle_hours"}.issubset(g.columns)
    assert g["busy_hours"].sum() > 0
    # the 59-minute wait for the user must land in idle, not busy
    assert g["idle_hours"].sum() > 0.5


def test_turnaround_uses_the_gap_to_the_next_step(data):
    tt = deep.turnaround_stats(data.turnarounds)
    row = tt[tt["tool"] == "run_command"].iloc[0]
    assert row["p50_seconds"] == pytest.approx(15.0)  # 10:00:05 -> 10:00:20


# --- commands -------------------------------------------------------------
def test_command_result_gives_duration_and_exit_code(data):
    assert len(data.commands) == 1
    row = data.commands.iloc[0]
    assert row["command"] == "uv run pytest -q"
    assert row["duration_seconds"] == pytest.approx(13.0)
    assert row["exit_code"] == 1


def test_non_command_content_with_stamps_is_rejected():
    # a file-read block has stamps but no exit code: pairing it invents durations
    duration, exit_code, note = deep._command_result(
        "Created At: 2026-10-05T10:00:00+00:00\nCompleted At: 2026-10-05T12:00:00+00:00\n"
        "File Path: `file:///x.md`\nTotal Lines: 10")
    assert duration is None and exit_code is None and note == ""


def test_command_result_rejects_implausible_windows():
    duration, _exit, note = deep._command_result(
        "Created At: 2026-10-05T10:00:00+00:00\nCompleted At: 2026-10-06T10:00:00+00:00\n"
        "The command exited with code 0.")
    assert duration is None and "implausible" in note


def test_exit_code_parsing_handles_cancellation():
    duration, exit_code, note = deep._command_result(
        "Created At: 2026-10-05T10:00:00+00:00\nCompleted At: 2026-10-05T10:00:05+00:00\n"
        "The task was canceled with result: Tool execution was canceled")
    assert duration == pytest.approx(5.0) and exit_code is None and note == "canceled"


# --- friction -------------------------------------------------------------
def test_failures_cover_error_status_and_error_message_steps(data):
    assert len(data.failures) == 2
    assert "target content not found" in " ".join(data.failures["text"])


def test_failure_text_is_a_message_not_a_bare_status(data):
    assert not data.failures["text"].isin(["DONE", "ERROR", "INVALID", ""]).any()
    assert (data.failures["text"].str.len() > 8).all()


def test_failure_summary_ranks_repeats(data):
    summary = deep.failure_summary(data.failures)
    assert summary.iloc[0]["count"] >= 1
    assert "last_seen" in summary.columns


def test_denials_capture_command_and_prompt_window(data):
    assert len(data.denials) == 1
    row = data.denials.iloc[0]
    assert row["wait_seconds"] == pytest.approx(60.0)
    assert "denied" in row["text"]


# --- model / workspaces ---------------------------------------------------
def test_model_switch_name_is_cleaned_of_boilerplate(data):
    assert len(data.model_switches) == 1
    assert data.model_switches.iloc[0]["to_model"] == "Claude Sonnet"


def test_workspace_comes_from_history_and_subagents_inherit_it(data):
    meta = data.session_meta.set_index("session_id")
    assert meta.loc[MAIN_ID, "workspace"] == WORKSPACE
    assert meta.loc[MAIN_ID, "project"] == "DemoProject"
    assert meta.loc[SUB_ID, "kind"] == "subagent"
    assert meta.loc[SUB_ID, "workspace"] == WORKSPACE  # inherited from the parent


def test_session_wall_clock(data):
    meta = data.session_meta.set_index("session_id")
    assert meta.loc[MAIN_ID, "wall_seconds"] == pytest.approx(3630.0)  # 10:00:00 -> 11:00:30


def test_workspace_totals_join_tokens_and_compute_cost(usage, data):
    ws = deep.workspace_totals(usage.sessions.assign(session_id=[MAIN_ID, "26082efd", "sub00001", "aaaabbbb"]),
                               data.session_meta, FLASH)
    assert not ws.empty
    real = ws[ws["project"] == "DemoProject"]
    assert len(real) == 1
    assert real.iloc[0]["cost_usd"] == pytest.approx(
        metrics.api_cost_usd(real.iloc[0]["fresh_in"], real.iloc[0]["cached"],
                             real.iloc[0]["output"], FLASH))


def test_workspace_totals_survive_missing_meta(usage):
    assert deep.workspace_totals(usage.sessions, pd.DataFrame(), FLASH).empty


# --- per-day counters -----------------------------------------------------
def test_step_days_counts_models_misses_thinking_and_checkpoints(data):
    # all three sessions are aggregated: 10 + 2 + 2 steps
    assert int(data.step_days["steps"].sum()) == 14
    assert int(data.step_days["model_calls"].sum()) == 9   # 5 main + 2 subagent + 2 other
    assert int(data.step_days["cache_miss_calls"].sum()) == 1  # only step 3 has cache_read = 0
    assert int(data.step_days["thinking_steps"].sum()) == 4
    assert int(data.step_days["checkpoints"].sum()) == 1
    assert len(data.step_days) == 3  # three calendar days


def test_counters_expose_tool_and_message_totals(data):
    assert data.counters["tool:search_web"] == 1
    assert data.counters["tool:ask_question"] == 1
    assert data.counters["subagent_dispatches"] == 1
    assert data.counters["messages_total"] == 1
    assert data.counters["messages_read"] == 1
    assert data.counters["tool_output_bytes"] == 2048
    assert data.counters["sessions_scanned"] == 3


def test_messages_parse_title_priority_and_receipt(data):
    msg = data.messages.iloc[0]
    assert msg["title"] == "Run pytest finished"
    assert msg["priority"] == "HIGH"
    assert bool(msg["read"]) is True
    assert msg["sender"] == "task-29"


def test_artifacts_are_read_from_the_session_root(data):
    assert len(data.artifacts) == 1
    art = data.artifacts.iloc[0]
    assert art["name"] == "walkthrough.md"
    assert bool(art["request_feedback"]) is True


# --- derived economics ----------------------------------------------------
def test_unit_economics_uses_measured_denominators(usage, data):
    overview = metrics.update_overview(usage.sessions, usage.daily, FLASH)
    busy = float(deep.gaps_daily(data.gaps)["busy_hours"].sum())
    eco = deep.unit_economics(overview, {"busy_hours": busy})
    assert eco["cost_per_call_usd"] == pytest.approx(overview.api_cost_usd / overview.totals.calls)
    assert eco["cost_per_busy_hour_usd"] == pytest.approx(overview.api_cost_usd / busy)
    assert eco["busy_hours"] == pytest.approx(busy)


def test_unit_economics_is_safe_with_no_busy_time(usage):
    overview = metrics.update_overview(usage.sessions, usage.daily, FLASH)
    eco = deep.unit_economics(overview, {"busy_hours": 0})
    assert eco["cost_per_busy_hour_usd"] == 0.0


def test_waste_estimate_is_bounded_by_the_observed_total(usage):
    overview = metrics.update_overview(usage.sessions, usage.daily, FLASH)
    small = deep.waste_estimate(overview, 5)
    assert 0 < small["cost_usd"] < overview.api_cost_usd
    huge = deep.waste_estimate(overview, 10 ** 9)   # more failures than calls cannot exceed 100%
    assert huge["cost_usd"] == pytest.approx(overview.api_cost_usd)
    assert huge["share_of_calls"] == 1.0


def test_missing_brain_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        deep.scan_deep(tmp_path / "nope")


def test_empty_brain_scans_cleanly(tmp_path):
    (tmp_path / "brain").mkdir()
    d = deep.scan_deep(tmp_path / "brain")
    assert d.empty
    assert d.tool_calls.empty and d.session_meta.empty
