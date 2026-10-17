"""Optional local SQLite snapshots.

Not used for the live view (a fresh scan is ~1.5 s and the logs keep changing);
used to keep a history of scans over time. Ingestion is idempotent: facts are
keyed by stable ids (session id, calendar date) and upserted, so re-running
extraction never duplicates a row.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at    TEXT NOT NULL,
    root        TEXT,
    sessions    INTEGER,
    calls       INTEGER,
    tokens      INTEGER
);
CREATE TABLE IF NOT EXISTS session_facts (
    session_id   TEXT PRIMARY KEY,
    label        TEXT,
    kind         TEXT,
    calls        INTEGER,
    fresh_in     INTEGER,
    cached       INTEGER,
    output       INTEGER,
    total        INTEGER,
    first_utc    TEXT,
    last_utc     TEXT,
    first_seen_at TEXT,
    last_updated_at TEXT
);
CREATE TABLE IF NOT EXISTS daily_facts (
    date        TEXT PRIMARY KEY,
    calls       INTEGER,
    sessions    INTEGER,
    fresh_in    INTEGER,
    cached      INTEGER,
    output      INTEGER,
    total       INTEGER,
    last_updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_facts(date);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    return conn


def _iso(dt) -> str | None:
    if dt is None or (isinstance(dt, float) and pd.isna(dt)):
        return None
    if isinstance(dt, str):
        return dt
    return str(dt)


def ingest(conn: sqlite3.Connection, usage, taken_at: datetime | None = None) -> dict:
    """Upsert one scan. Returns row counts. Calling twice with the same data
    leaves the table contents unchanged (idempotent)."""
    taken = (taken_at or datetime.now(timezone.utc)).astimezone().isoformat()
    sessions = usage.sessions
    daily = usage.daily
    now = taken

    srows = [
        (r.session_id, r.label, r.kind, int(r.calls), int(r.fresh_in), int(r.cached),
         int(r.output), int(r.total), _iso(r.first_utc), _iso(r.last_utc), now, now)
        for r in (sessions.itertuples() if sessions is not None and not sessions.empty else [])
    ]
    drows = []
    if daily is not None and not daily.empty:
        for r in daily.itertuples():
            drows.append((pd.Timestamp(r.date).date().isoformat(), int(r.calls), int(r.sessions),
                          int(r.fresh_in), int(r.cached), int(r.output), int(r.total), now))

    with conn:
        conn.executemany(
            """INSERT INTO session_facts
               (session_id,label,kind,calls,fresh_in,cached,output,total,first_utc,last_utc,
                first_seen_at,last_updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(session_id) DO UPDATE SET
                 label=excluded.label, kind=excluded.kind, calls=excluded.calls,
                 fresh_in=excluded.fresh_in, cached=excluded.cached, output=excluded.output,
                 total=excluded.total, first_utc=excluded.first_utc, last_utc=excluded.last_utc,
                 last_updated_at=excluded.last_updated_at""",
            srows,
        )
        conn.executemany(
            """INSERT INTO daily_facts
               (date,calls,sessions,fresh_in,cached,output,total,last_updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 calls=excluded.calls, sessions=excluded.sessions, fresh_in=excluded.fresh_in,
                 cached=excluded.cached, output=excluded.output, total=excluded.total,
                 last_updated_at=excluded.last_updated_at""",
            drows,
        )
        conn.execute(
            "INSERT INTO runs (taken_at,root,sessions,calls,tokens) VALUES (?,?,?,?,?)",
            (taken, usage.root, len(srows), int(sum(r[3] for r in srows)),
             int(sum(r[7] for r in srows))),
        )
    return {"sessions": len(srows), "days": len(drows), "taken_at": taken}


def counts(conn: sqlite3.Connection) -> dict:
    def one(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])
    return {
        "session_facts": one("SELECT COUNT(*) FROM session_facts"),
        "daily_facts": one("SELECT COUNT(*) FROM daily_facts"),
        "runs": one("SELECT COUNT(*) FROM runs"),
    }


def load_daily(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM daily_facts ORDER BY date", conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_sessions(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM session_facts ORDER BY total DESC", conn)


def runs(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM runs ORDER BY run_id DESC", conn)


def last_success(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(taken_at) FROM runs").fetchone()
    return row[0] if row and row[0] else None
