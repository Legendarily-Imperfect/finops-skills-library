"""sync-check tests: every block rule fires, and unrecognized input fails loudly."""

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from check_sync import check, DEFAULT_PATTERNS

CLEAN = [
    "2026-08-26 clearing period 2026-08",
    "2026-08-26 wrote 4210 rows into period 2026-08",
    "sync complete for 2026-08 at 2026-08-26T02:00:00Z",
]


def run(lines, since=None, closed_before=None):
    return check(lines, DEFAULT_PATTERNS, since, closed_before)


def test_clean_run_passes():
    r = run(CLEAN, since=date(2026, 8, 25), closed_before="2026-07")
    assert r["verdict"] == "PASS" and r["recognized"] == 3


def test_stale_blocks():
    r = run(CLEAN, since=date(2026, 8, 27))
    assert r["verdict"] == "BLOCK"
    assert any(b["rule"] == "stale" for b in r["blocks"])


def test_no_sync_complete_at_all_is_stale():
    r = run(["clearing period 2026-08", "wrote 10 rows into period 2026-08"],
            since=date(2026, 8, 1))
    assert any(b["rule"] == "stale" for b in r["blocks"])


def test_skipped_clear_blocks():
    r = run(["wrote 4210 rows into period 2026-08",
             "sync complete for 2026-08 at 2026-08-26T02:00:00Z"])
    assert any(b["rule"] == "skipped_clear" for b in r["blocks"])


def test_clear_after_write_still_blocks():
    """Order matters: clearing AFTER the write is not clear-then-write."""
    r = run(["wrote 10 rows into period 2026-08", "clearing period 2026-08"])
    assert any(b["rule"] == "skipped_clear" for b in r["blocks"])


def test_closed_period_blocks():
    r = run(["clearing period 2026-06", "wrote 99 rows into period 2026-06",
             "sync complete for 2026-06 at 2026-08-26T02:00:00Z"],
            closed_before="2026-07")
    assert any(b["rule"] == "closed_period" for b in r["blocks"])


def test_unrecognized_input_fails_loudly():
    r = run(["INFO something happened", "DEBUG heartbeat ok", "totally unrelated"])
    assert r["verdict"] == "NOTHING_RECOGNIZED"
    assert r["recognized"] == 0


def test_multiple_blocks_all_reported():
    r = run(["wrote 10 rows into period 2026-05",
             "wrote 10 rows into period 2026-08"],
            since=date(2026, 8, 25), closed_before="2026-07")
    rules = {b["rule"] for b in r["blocks"]}
    assert {"stale", "skipped_clear", "closed_period"} <= rules
