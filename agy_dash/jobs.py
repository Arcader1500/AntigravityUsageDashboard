"""Running the existing extractor as a background process.

The dashboard never freezes waiting for extraction: the job is started, polled
from the UI, and its stdout/stderr/exit code are shown when it finishes.

Safety rules:
  * argv list, never shell=True, never string interpolation of user input.
  * the report name comes from a fixed whitelist.
  * a lock file prevents accidental concurrent runs (including from a second tab).
  * output goes to files, so a large report can never deadlock a full pipe buffer.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPORTS = ("all", "daily", "sessions", "tips")

# Windows: keep the child from flashing a console window.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class JobState:
    status: str = "idle"  # idle | running | success | failed | timeout | error
    started_at: datetime | None = None
    ended_at: datetime | None = None
    exit_code: int | None = None
    command: list[str] = field(default_factory=list)
    stdout_path: str | None = None
    stderr_path: str | None = None
    message: str = ""
    report: str = "all"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.ended_at or datetime.now(self.started_at.tzinfo)
        return (end - self.started_at).total_seconds()

    @property
    def running(self) -> bool:
        return self.status == "running"

    def read_stdout(self, limit: int | None = None) -> str:
        return _read(self.stdout_path, limit)

    def read_stderr(self, limit: int | None = None) -> str:
        return _read(self.stderr_path, limit)


def _read(path: str | None, limit: int | None) -> str:
    if not path or not Path(path).exists():
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:] if limit else text


def acquire_lock(lock_path: Path, stale_after_seconds: int = 3_600) -> bool:
    """Create the lock exclusively. A lock older than stale_after_seconds is
    treated as abandoned (crashed run) and replaced."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            age = 0
        if age < stale_after_seconds:
            return False
        lock_path.unlink(missing_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except OSError:
        return False


def release_lock(lock_path: Path) -> None:
    Path(lock_path).unlink(missing_ok=True)


class JobRunner:
    """Single-job runner. One instance is kept per Streamlit session."""

    def __init__(self, script_path: Path, python_executable: str, *, table=None,
                 log_dir: Path | None = None, timeout_seconds: int = 180,
                 lock_path: Path | None = None, last_run_path: Path | None = None):
        self.script_path = Path(script_path)
        self.python_executable = python_executable
        self.table = table if table is not None else dict(os.environ)
        self.log_dir = Path(log_dir) if log_dir else Path(script_path).parent
        self.timeout_seconds = int(timeout_seconds)
        self.lock_path = Path(lock_path) if lock_path else self.log_dir / ".extract.lock"
        self.last_run_path = Path(last_run_path) if last_run_path else self.log_dir / "last_run.json"
        self.state = JobState()
        self._proc: subprocess.Popen | None = None
        self._out_fh = None
        self._err_fh = None

    # --- start / poll -----------------------------------------------------
    def start(self, report: str = "all", extra_args: list[str] | None = None) -> JobState:
        if self._proc is not None and self._proc.poll() is None:
            self.state.message = "already running"
            return self.state
        if report not in REPORTS:
            self.state = JobState(status="error", message=f"unknown report {report!r}")
            return self.state
        if not self.script_path.exists():
            self.state = JobState(status="error", message=f"extractor not found: {self.script_path}")
            return self.state
        if not acquire_lock(self.lock_path, stale_after_seconds=max(self.timeout_seconds * 2, 300)):
            self.state = JobState(status="error",
                                  message="another extraction is already running (lock file present)")
            return self.state

        self.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = self.log_dir / f"extract-{stamp}.out"
        err_path = self.log_dir / f"extract-{stamp}.err"
        cmd = [self.python_executable, str(self.script_path), report] + list(extra_args or [])
        try:
            self._out_fh = out_path.open("w", encoding="utf-8", errors="replace")
            self._err_fh = err_path.open("w", encoding="utf-8", errors="replace")
            self._proc = subprocess.Popen(
                cmd, stdout=self._out_fh, stderr=self._err_fh, stdin=subprocess.DEVNULL,
                cwd=str(self.script_path.parent), env=self.table,
                creationflags=_NO_WINDOW,
            )
        except OSError as exc:
            self._close_files()
            release_lock(self.lock_path)
            self.state = JobState(status="error", message=f"could not start extractor: {exc}")
            return self.state

        self.state = JobState(
            status="running", started_at=datetime.now().astimezone(),
            command=cmd, stdout_path=str(out_path), stderr_path=str(err_path), report=report,
            message="extraction started",
        )
        return self.state

    def poll(self) -> JobState:
        if self.state.status != "running":
            return self.state
        assert self._proc is not None
        code = self._proc.poll()
        if code is None:
            started = self.state.started_at
            if started and (datetime.now(started.tzinfo) - started).total_seconds() > self.timeout_seconds:
                self._terminate()
                self._finish("timeout", code=None,
                             message=f"timed out after {self.timeout_seconds}s and was killed")
            return self.state
        self._close_files()
        status = "success" if code == 0 else "failed"
        self._finish(status, code=code, message=f"exit code {code}")
        return self.state

    def _terminate(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass
        self._close_files()

    def _finish(self, status: str, *, code: int | None, message: str) -> None:
        self.state.status = status
        self.state.ended_at = datetime.now().astimezone()
        self.state.exit_code = code
        self.state.message = message
        release_lock(self.lock_path)
        record = {
            "status": status, "exit_code": code, "report": self.state.report,
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "ended_at": self.state.ended_at.isoformat(),
            "duration_seconds": round(self.state.duration_seconds or 0.0, 2),
            "command": self.state.command,
            "message": message,
        }
        try:
            self.last_run_path.parent.mkdir(parents=True, exist_ok=True)
            self.last_run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _close_files(self) -> None:
        for fh in (self._out_fh, self._err_fh):
            try:
                if fh:
                    fh.close()
            except OSError:
                pass
        self._out_fh = self._err_fh = None


def last_run(path: Path) -> dict | None:
    """The persisted record of the most recent extraction attempt."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
