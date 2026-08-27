"""Tests for gcp-billing-pull: the partition discipline is the product."""

from datetime import date
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from gcp_pull import build_sql, resolve_window, PARTITION_PAD_DAYS


def test_sql_filters_both_partition_and_usage():
    sql = build_sql("p", "d", "t", date(2026, 6, 1), date(2026, 6, 10))
    assert "_PARTITIONTIME >=" in sql and "_PARTITIONTIME <" in sql
    assert "usage_start_time >=" in sql and "usage_start_time <" in sql


def test_partition_window_pads_both_sides():
    sql = build_sql("p", "d", "t", date(2026, 6, 1), date(2026, 6, 10))
    assert f"TIMESTAMP('{date(2026, 5, 30).isoformat()}')" in sql          # start - pad
    assert f"TIMESTAMP('{date(2026, 6, 13).isoformat()}')" in sql          # end + 1 + pad
    assert PARTITION_PAD_DAYS == 2


def test_usage_window_is_exact_half_open():
    sql = build_sql("p", "d", "t", date(2026, 6, 1), date(2026, 6, 10))
    assert "usage_start_time >= TIMESTAMP('2026-06-01')" in sql
    assert "usage_start_time <  TIMESTAMP('2026-06-11')" in sql


def test_columns_match_normalize_mapping_fingerprint():
    """The emitted aliases must satisfy focus-normalize's gcp_billing mapping,
    or the two tools drift apart and the pipeline breaks at the seam."""
    import json
    mapping = json.loads(
        (Path(__file__).parents[2] / "normalizers" / "focus-normalize" / "mappings" / "gcp_billing.json")
        .read_text(encoding="utf-8"))
    sql = build_sql("p", "d", "t", date(2026, 6, 1), date(2026, 6, 2))
    for source_col in mapping["columns"]:
        assert source_col in sql, f"mapping expects {source_col!r}, SQL does not emit it"
    assert mapping["tag_json_column"] in sql


def test_trailing_window_ends_yesterday():
    start, end = resolve_window(days=10, start=None, end=None, today=date(2026, 6, 30))
    assert end == date(2026, 6, 29)
    assert start == date(2026, 6, 20)
    assert (end - start).days == 9


def test_explicit_window_passthrough():
    start, end = resolve_window(None, "2026-05-01", "2026-05-31")
    assert (start, end) == (date(2026, 5, 1), date(2026, 5, 31))


def test_half_window_is_error():
    with pytest.raises(SystemExit):
        resolve_window(None, "2026-05-01", None)


def test_reversed_dates_error():
    with pytest.raises(SystemExit):
        build_sql("p", "d", "t", date(2026, 6, 10), date(2026, 6, 1))


def test_emit_sql_needs_no_gcp(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "gcp_pull.py"),
         "--project", "p", "--dataset", "d", "--table", "t",
         "--start", "2026-06-01", "--end", "2026-06-10", "--emit-sql"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "SELECT" in proc.stdout and "_PARTITIONTIME" in proc.stdout
