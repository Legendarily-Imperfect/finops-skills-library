"""otel-token-pull tests: the four telemetry rules, each asserted."""

from datetime import datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from otel_pull import build_promql, bucket_starts, collect, model_family


def test_promql_uses_sum_over_time_never_rate():
    q = build_promql("claude_code.token.usage")
    assert "sum_over_time" in q
    assert "rate(" not in q and "increase(" not in q


def test_promql_quotes_dotted_names():
    q = build_promql("claude_code.token.usage", user="a@b.com")
    assert '__name__="claude_code.token.usage"' in q
    assert '"user.email"="a@b.com"' in q
    assert "claude_code_token_usage" not in q  # underscored form returns zero series


def test_bucket_count_and_alignment():
    end = datetime(2026, 6, 30, 12, 34, 56)
    buckets = bucket_starts(end, 24)
    assert len(buckets) == 24  # exactly the window, no midnight extra
    assert buckets[-1] == datetime(2026, 6, 30, 12, 0, 0)
    assert all(b.minute == 0 and b.second == 0 for b in buckets)


def test_prezeroed_idle_buckets_are_zero_not_missing():
    buckets = bucket_starts(datetime(2026, 6, 30, 12), 3)
    series = [{"metric": {"user.email": "a@b.com", "model": "claude-opus-5"},
               "values": [[buckets[1].timestamp() + 0, "500"]]}]
    # timestamps: collect matches naive UTC datetimes
    series[0]["values"] = [[datetime(2026, 6, 30, 11).replace(
        tzinfo=None).timestamp(), "500"]]
    import calendar
    ts = calendar.timegm(datetime(2026, 6, 30, 11).timetuple())
    series[0]["values"] = [[ts, "500"]]
    rows = collect(series, buckets)
    assert len(rows) == 3  # every bucket present for the one (user, model)
    tokens = {r["bucket_start"]: r["tokens"] for r in rows}
    assert tokens["2026-06-30T11:00:00Z"] == 500
    assert tokens["2026-06-30T10:00:00Z"] == 0
    assert tokens["2026-06-30T12:00:00Z"] == 0


def test_model_family_collapses_the_four_spellings():
    spellings = ["claude-opus-5[1m]", "claude-haiku-4-5-20251001",
                 "claude-haiku-4-5@20251001", "claude-haiku-4-5"]
    fams = {model_family(s) for s in spellings[1:]}
    assert fams == {"claude-haiku-4-5"}
    assert model_family(spellings[0]) == "claude-opus-5"


def test_model_raw_kept_beside_family():
    buckets = bucket_starts(datetime(2026, 6, 30, 12), 1)
    series = [{"metric": {"user.email": "a@b.com", "model": "claude-haiku-4-5@20251001"},
               "values": []}]
    rows = collect(series, buckets)
    assert rows[0]["model_raw"] == "claude-haiku-4-5@20251001"
    assert rows[0]["model_family"] == "claude-haiku-4-5"
