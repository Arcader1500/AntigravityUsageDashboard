"""SQLite snapshots: idempotent ingestion, upserts, history."""

from __future__ import annotations

from datetime import datetime, timezone

from agy_dash import snapshots
from agy_dash.source import UsageData


def test_ingest_is_idempotent(usage, tmp_path):
    conn = snapshots.connect(tmp_path / "s.db")
    snapshots.ingest(conn, usage)
    first = snapshots.counts(conn)
    totals_first = snapshots.load_daily(conn)["total"].sum()

    snapshots.ingest(conn, usage)  # a rerun must not duplicate historical records
    second = snapshots.counts(conn)

    assert first["session_facts"] == second["session_facts"] == len(usage.sessions)
    assert first["daily_facts"] == second["daily_facts"] == len(usage.daily)
    assert second["runs"] == first["runs"] + 1  # runs are a log, facts are the state
    assert snapshots.load_daily(conn)["total"].sum() == totals_first
    conn.close()


def test_ingest_updates_changed_rows_without_adding_new_ones(usage, tmp_path):
    conn = snapshots.connect(tmp_path / "s.db")
    snapshots.ingest(conn, usage, taken_at=datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc))

    grown = usage.daily.copy()
    grown.loc[0, "fresh_in"] = grown.loc[0, "fresh_in"] + 1_000
    grown.loc[0, "total"] = grown.loc[0, "total"] + 1_000
    snapshots.ingest(conn, UsageData(usage.sessions, grown, usage.scanned_at, usage.root, []),
                     taken_at=datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc))

    assert snapshots.counts(conn)["daily_facts"] == len(usage.daily)
    row = snapshots.load_daily(conn).iloc[0]
    assert row["fresh_in"] == usage.daily.iloc[0]["fresh_in"] + 1_000
    conn.close()


def test_last_success_tracks_the_most_recent_scan(usage, tmp_path):
    conn = snapshots.connect(tmp_path / "s.db")
    assert snapshots.last_success(conn) is None
    snapshots.ingest(conn, usage, taken_at=datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc))
    later = snapshots.ingest(conn, usage, taken_at=datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc))
    assert snapshots.last_success(conn) == later["taken_at"]
    conn.close()


def test_sessions_survive_a_reconnect(usage, tmp_path):
    path = tmp_path / "s.db"
    conn = snapshots.connect(path)
    snapshots.ingest(conn, usage)
    conn.close()
    conn2 = snapshots.connect(path)
    assert len(snapshots.load_sessions(conn2)) == len(usage.sessions)
    conn2.close()
