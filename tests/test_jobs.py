"""Extraction process handling: success, failure, timeout, concurrency, errors."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from agy_dash import jobs

FAKE = '''\
import sys, time
mode = sys.argv[1]
if mode == "all":
    print("extraction ok"); sys.exit(0)
if mode == "daily":
    print("boom", file=sys.stderr); sys.exit(3)
if mode == "sessions":
    time.sleep(60)
print("tips ran"); sys.exit(0)
'''


@pytest.fixture
def fake_script(tmp_path) -> Path:
    p = tmp_path / "fake_extractor.py"
    p.write_text(FAKE, encoding="utf-8")
    return p


def make_runner(tmp_path, script, **kw) -> jobs.JobRunner:
    return jobs.JobRunner(script, sys.executable, table=dict(os.environ),
                          log_dir=tmp_path / "logs", timeout_seconds=kw.pop("timeout", 30), **kw)


def wait_for(runner: jobs.JobRunner, seconds: float = 20.0):
    end = time.time() + seconds
    while runner.state.running and time.time() < end:
        time.sleep(0.05)
        runner.poll()
    return runner.state


def test_successful_run_reports_exit_code_and_stdout(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    runner.start("all")
    state = wait_for(runner)
    assert state.status == "success"
    assert state.exit_code == 0
    assert "extraction ok" in state.read_stdout()
    assert state.started_at and state.ended_at
    assert state.duration_seconds is not None and state.duration_seconds >= 0


def test_failed_run_reports_stderr_and_nonzero_exit(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    runner.start("daily")
    state = wait_for(runner)
    assert state.status == "failed" and state.exit_code == 3
    assert "boom" in state.read_stderr()


def test_timeout_kills_the_process_and_marks_timeout(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script, timeout=1)
    runner.start("sessions")
    state = wait_for(runner, seconds=20)
    assert state.status == "timeout"
    assert "timed out" in state.message
    assert not runner.state.running


def test_a_second_run_is_refused_while_one_is_in_flight(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script, timeout=1)
    runner.start("sessions")
    again = runner.start("all")
    assert again.status == "running"  # unchanged state, no second process
    assert again.message == "already running"
    wait_for(runner, seconds=20)  # let the timeout clean up


def test_lock_file_blocks_a_different_runner_instance(tmp_path, fake_script):
    a = make_runner(tmp_path, fake_script, timeout=1)
    b = make_runner(tmp_path, fake_script, timeout=1)
    a.start("sessions")
    state = b.start("all")
    assert state.status == "error"
    assert "already running" in state.message
    wait_for(a, seconds=20)


def test_lock_is_released_after_a_run(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    runner.start("all")
    wait_for(runner)
    assert not Path(runner.lock_path).exists()
    # and a new run can start again
    runner.start("all")
    assert wait_for(runner).status == "success"


def test_stale_lock_is_replaced(tmp_path):
    lock = tmp_path / "logs" / ".extract.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("99999", encoding="utf-8")
    old = time.time() - 7200
    os.utime(lock, (old, old))
    assert jobs.acquire_lock(lock, stale_after_seconds=60) is True
    assert jobs.acquire_lock(lock, stale_after_seconds=60) is False  # fresh lock now held
    jobs.release_lock(lock)
    assert not lock.exists()


def test_missing_script_reports_error_instead_of_raising(tmp_path):
    runner = make_runner(tmp_path, tmp_path / "nope.py")
    state = runner.start("all")
    assert state.status == "error" and "not found" in state.message


def test_unknown_report_is_rejected(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    state = runner.start("rm -rf /")
    assert state.status == "error"
    assert "unknown report" in state.message


def test_command_is_an_argv_list_with_no_shell(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    runner.start("all")
    assert runner.state.command[0] == sys.executable
    assert runner.state.command[-1] == "all"
    assert all(isinstance(part, str) for part in runner.state.command)
    wait_for(runner)


def test_last_run_record_is_written(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    runner.start("all")
    wait_for(runner)
    rec = jobs.last_run(runner.last_run_path)
    assert rec["status"] == "success" and rec["exit_code"] == 0
    assert rec["report"] == "all" and rec["duration_seconds"] >= 0


def test_last_run_missing_file_is_not_an_error(tmp_path, fake_script):
    runner = make_runner(tmp_path, fake_script)
    assert jobs.last_run(runner.last_run_path) is None


def test_output_uses_the_configured_log_location(tmp_path, fake_script):
    log_dir = tmp_path / "custom_logs"
    runner = jobs.JobRunner(fake_script, sys.executable, table=dict(os.environ), log_dir=log_dir)
    runner.start("all")
    wait_for(runner)
    assert Path(runner.state.stdout_path).parent == log_dir
    assert (log_dir / "last_run.json").exists()
