"""Source loading: extractor reuse, normalization, filtering, error handling."""

from __future__ import annotations

import pandas as pd
import pytest

from agy_dash import source

FAKE_EXTRACTOR = '''\
from datetime import datetime, timezone

def scan(root):
    sessions = {
        "sess-main": {"steps": 2, "in": 100, "cache": 10, "out": 5, "total": 115,
                      "first": datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc),
                      "last": datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),
                      "kind": "main", "label": "hello world"},
        "sess-sub": {"steps": 1, "in": 7, "cache": 0, "out": 3, "total": 10,
                     "first": None, "last": None, "kind": "other", "label": ""},
    }
    daily = {"2026-10-05": {"steps": 3, "in": 107, "cache": 10, "out": 8,
                            "sessions": {"sess-main", "sess-sub"}}}
    return sessions, daily
'''


@pytest.fixture
def fake_extractor(tmp_path):
    p = tmp_path / "agy_usage.py"
    p.write_text(FAKE_EXTRACTOR, encoding="utf-8")
    return p


@pytest.fixture
def brain(tmp_path):
    d = tmp_path / "brain"
    d.mkdir()
    return d


def test_scan_usage_normalizes_extractor_output(brain, fake_extractor):
    data = source.scan_usage(brain, fake_extractor)
    assert list(data.sessions.columns) == source.SESSION_COLUMNS
    assert list(data.daily.columns) == source.DAILY_COLUMNS
    assert len(data.sessions) == 2 and len(data.daily) == 1

    row = data.sessions.set_index("session_id").loc["sess-main"]
    assert row["total"] == 115
    assert row["fresh_in"] + row["cached"] + row["output"] == row["total"]
    assert row["first_date"] == "2026-10-05"
    assert row["label"] == "hello world"

    day = data.daily.iloc[0]
    assert day["total"] == 125 and day["calls"] == 3 and day["sessions"] == 2
    assert isinstance(day["date"], pd.Timestamp)


def test_missing_brain_directory_raises_readable_error(tmp_path, fake_extractor):
    with pytest.raises(source.SourceError, match="brain directory not found"):
        source.scan_usage(tmp_path / "nope", fake_extractor)


def test_missing_extractor_raises_readable_error(brain, tmp_path):
    with pytest.raises(source.SourceError, match="extractor script not found"):
        source.scan_usage(brain, tmp_path / "missing.py")


def test_unlabeled_session_is_tolerated(brain, fake_extractor):
    data = source.scan_usage(brain, fake_extractor)
    assert "(unlabeled)" in set(data.sessions["label"])


def test_clip_dates_is_inclusive(usage):
    got = source.clip_dates(usage.daily, pd.Timestamp("2026-10-08"), pd.Timestamp("2026-10-15"))
    assert list(got["date"]) == [pd.Timestamp("2026-10-08"), pd.Timestamp("2026-10-15")]


def test_sessions_touching_keeps_overlapping_sessions(usage):
    got = source.sessions_touching(usage.sessions, pd.Timestamp("2026-10-08"), pd.Timestamp("2026-10-08"))
    assert set(got["session_id"]) == {"26082efd", "sub00001"}
    all_sessions = source.sessions_touching(usage.sessions, None, None)
    assert len(all_sessions) == len(usage.sessions)


def test_empty_result_is_flagged_not_crashed(brain, tmp_path):
    extractor = tmp_path / "empty.py"
    extractor.write_text("def scan(root):\n    return {}, {}\n", encoding="utf-8")
    data = source.scan_usage(brain, extractor)
    assert data.empty and data.warnings
