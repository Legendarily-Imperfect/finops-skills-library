"""Tests for focus-conform: each rule fires, exit codes are honest."""

import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conform import check, REQUIRED_COLUMNS

SAMPLE = Path(__file__).parents[2] / "synthetic-data" / "sample" / "billing.csv"

BASE = {
    "BillingAccountId": "acct", "ChargePeriodStart": "2026-06-01", "ChargePeriodEnd": "2026-06-02",
    "BilledCost": "1.50", "BillingCurrency": "USD", "ChargeCategory": "Usage",
    "ProviderName": "AWS", "ServiceName": "Amazon EC2", "Tags": "{}",
}


def write_csv(path, rows):
    cols = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path


def violations_for(tmp_path, **overrides):
    row = {**BASE, **overrides}
    p = write_csv(tmp_path / "t.csv", [row])
    v, _ = check(p, max_examples=5)
    return v


def test_clean_row_passes(tmp_path):
    assert violations_for(tmp_path) == []


def test_missing_required_column(tmp_path):
    row = {k: v for k, v in BASE.items() if k != "BilledCost"}
    p = write_csv(tmp_path / "t.csv", [row])
    v, _ = check(p, max_examples=5)
    assert len(v) == 1 and "BilledCost" in v[0]


def test_scientific_notation_is_violation(tmp_path):
    v = violations_for(tmp_path, BilledCost="1.5E-7")
    assert any("money format" in x for x in v)


def test_currency_symbol_is_violation(tmp_path):
    v = violations_for(tmp_path, BilledCost="$1,234.00")
    assert any("money format" in x for x in v)


def test_bad_date_is_violation(tmp_path):
    v = violations_for(tmp_path, ChargePeriodStart="06/01/2026")
    assert any("date format" in x for x in v)


def test_unknown_charge_category(tmp_path):
    v = violations_for(tmp_path, ChargeCategory="Mystery")
    assert any("ChargeCategory" in x for x in v)


def test_tags_array_is_violation(tmp_path):
    v = violations_for(tmp_path, Tags='[{"key":"a"}]')
    assert any("Tags not a JSON object" in x for x in v)


def test_money_without_currency(tmp_path):
    v = violations_for(tmp_path, BillingCurrency="")
    assert any("without BillingCurrency" in x for x in v)


def test_synthetic_sample_conforms_exit_zero():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "conform.py"), "--in", str(SAMPLE)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_exit_code_two_on_violation(tmp_path):
    p = write_csv(tmp_path / "bad.csv", [{**BASE, "BilledCost": "oops"}])
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "conform.py"), "--in", str(p)],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "VIOLATION" in proc.stdout
