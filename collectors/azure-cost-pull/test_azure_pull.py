"""azure-cost-pull tests: latest-run selection and locale refusal."""

import csv
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from azure_pull import pick_latest, sniff_decimal_comma


BLOBS = [
    "daily-costs/20260601-20260630/run_20260615T020000Z/part_0.csv",
    "daily-costs/20260601-20260630/run_20260616T020000Z/part_0.csv",
    "daily-costs/20260601-20260630/run_20260614T020000Z/part_0.csv",
    "daily-costs/20260501-20260531/run_20260616T020000Z/part_0.csv",
]


def test_latest_run_wins_not_the_folder():
    chosen = pick_latest(BLOBS, "2026-06")
    assert "run_20260616T020000Z" in chosen
    assert "20260601-20260630" in chosen


def test_other_periods_never_selected():
    chosen = pick_latest(BLOBS, "2026-05")
    assert "20260501-20260531" in chosen


def test_no_match_is_error():
    with pytest.raises(SystemExit):
        pick_latest(BLOBS, "2026-07")


def write_costs(tmp_path, values):
    p = tmp_path / "azure.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["CostInBillingCurrency"], lineterminator="\n")
        w.writeheader()
        for v in values:
            w.writerow({"CostInBillingCurrency": v})
    return p


def test_decimal_comma_detected(tmp_path):
    assert sniff_decimal_comma(write_costs(tmp_path, ["12,50", "3,75", "8,00"])) is True


def test_decimal_dot_passes(tmp_path):
    assert sniff_decimal_comma(write_costs(tmp_path, ["12.50", "3.75", "8"])) is False


def test_seam_with_focus_normalize_mapping():
    """The azure_cost mapping's fingerprint must be standard export columns."""
    import json
    mapping = json.loads(
        (Path(__file__).parents[2] / "normalizers" / "focus-normalize" /
         "mappings" / "azure_cost.json").read_text(encoding="utf-8"))
    standard = {"CostInBillingCurrency", "Date", "MeterCategory", "SubscriptionId",
                "BillingAccountId", "BillingAccountName", "SubscriptionName",
                "BillingPeriodStartDate", "BillingPeriodEndDate", "BillingCurrencyCode",
                "ChargeType", "ProductName", "MeterSubCategory", "ResourceId",
                "ResourceName", "ResourceLocation", "Quantity", "UnitOfMeasure",
                "MeterId", "Tags"}
    for col in mapping["fingerprint"]:
        assert col in standard
    for col in mapping["columns"]:
        assert col in standard, f"mapping names non-standard export column {col!r}"
