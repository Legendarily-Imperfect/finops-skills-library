"""llm-spend-caps tests: fail closed, Decimal exact, deny names its numbers."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from caps import check, load_config, load_month, money, record, status

TODAY = date(2026, 6, 15)

CONFIG = {
    "pool_monthly_cap": Decimal("100.00"),
    "per_user_monthly_cap": Decimal("30.00"),
    "user_overrides": {"ci-bot": Decimal("60.00")},
}


def write_ledger(path: Path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def test_bare_number_amount_is_fatal(tmp_path):
    cfg = tmp_path / "caps.json"
    cfg.write_text('{"pool_monthly_cap": 100, "per_user_monthly_cap": "30.00"}',
                   encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(str(cfg))
    with pytest.raises(SystemExit):
        money(100)


def test_allow_under_both_caps(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [{"date": "2026-06-01", "user": "alice", "cost": "10.00"}])
    v = check(CONFIG, str(ledger), "alice", money("5.00"), TODAY)
    assert v["allow"] is True
    assert v["user_remaining"] == "15.00"
    assert v["pool_remaining"] == "85.00"


def test_user_cap_denies_even_with_pool_room(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [{"date": "2026-06-01", "user": "alice", "cost": "28.00"}])
    v = check(CONFIG, str(ledger), "alice", money("3.00"), TODAY)
    assert v["allow"] is False and v["cap"] == "user"
    assert v["spent"] == "28.00" and v["limit"] == "30.00" and v["estimate"] == "3.00"


def test_pool_cap_denies_across_users(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [
        {"date": "2026-06-01", "user": "ci-bot", "cost": "55.00"},
        {"date": "2026-06-02", "user": "alice", "cost": "25.00"},
        {"date": "2026-06-03", "user": "bob", "cost": "18.00"},
    ])
    v = check(CONFIG, str(ledger), "carol", money("5.00"), TODAY)
    assert v["allow"] is False and v["cap"] == "pool"
    assert v["spent"] == "98.00" and v["limit"] == "100.00"


def test_exact_boundary_allows_over_denies(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [{"date": "2026-06-01", "user": "alice", "cost": "25.00"}])
    assert check(CONFIG, str(ledger), "alice", money("5.00"), TODAY)["allow"] is True
    assert check(CONFIG, str(ledger), "alice", money("5.01"), TODAY)["allow"] is False


def test_override_beats_default_cap(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [{"date": "2026-06-01", "user": "ci-bot", "cost": "45.00"}])
    v = check(CONFIG, str(ledger), "ci-bot", money("10.00"), TODAY)
    assert v["allow"] is True  # 55 <= 60 override; default 30 would have denied long ago


def test_month_rollover_forgets_last_month(tmp_path):
    ledger = tmp_path / "l.jsonl"
    write_ledger(ledger, [
        {"date": "2026-05-31", "user": "alice", "cost": "29.99"},
        {"date": "2026-06-01", "user": "alice", "cost": "1.00"},
    ])
    pool, per_user = load_month(str(ledger), "2026-06")
    assert pool == Decimal("1.00") and per_user == {"alice": Decimal("1.00")}


def test_corrupt_ledger_fails_closed(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ledger.write_text('{"date": "2026-06-01", "user": "alice", "cost": "1.00"}\n'
                      'not json at all\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        check(CONFIG, str(ledger), "alice", money("1.00"), TODAY)
    ledger.write_text('{"date": "2026-06-01", "user": "alice", "cost": 1.0}\n',
                      encoding="utf-8")
    with pytest.raises(SystemExit):  # bare-number cost in the ledger is also corrupt
        check(CONFIG, str(ledger), "alice", money("1.00"), TODAY)


def test_record_then_status_is_decimal_exact(tmp_path):
    ledger = tmp_path / "l.jsonl"
    for _ in range(3):
        record(str(ledger), "alice", money("0.10"), TODAY)
    s = status(CONFIG, str(ledger), TODAY)
    assert s["users"]["alice"]["spent"] == "0.30"  # float would give 0.30000000000000004
    assert s["pool"]["remaining"] == "99.70"


def test_missing_ledger_is_zero_spend_not_error(tmp_path):
    v = check(CONFIG, str(tmp_path / "absent.jsonl"), "alice", money("1.00"), TODAY)
    assert v["allow"] is True
