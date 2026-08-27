"""commitment-coverage tests, against the sample's planted unused commitments."""

import csv
import json
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from coverage import analyze, DEFAULT_ELIGIBLE

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gt():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_planted_unused_commitments_named_with_exact_dollars():
    result = analyze(sample_rows(), DEFAULT_ELIGIBLE)
    expected = {c["id"]: c["cost"] for c in gt()["unused_commitments"]}
    actual = {u["id"]: u["dollars"] for u in result["unused_commitments"]}
    assert actual == expected


def test_sample_has_zero_coverage_and_zero_utilization():
    """The sample plants purchases with no matching usage: the honest read is
    0% coverage and 0% utilization, not a green dashboard."""
    result = analyze(sample_rows(), DEFAULT_ELIGIBLE)
    assert result["coverage_pct"] == "0.0"
    assert result["utilization_pct"] == "0.0"


def test_covered_usage_moves_both_numbers():
    rows = [
        {"ChargeCategory": "Usage", "ServiceCategory": "Compute", "BilledCost": "60.00",
         "CommitmentDiscountId": "c-1", "CommitmentDiscountStatus": "Used",
         "ProviderName": "AWS"},
        {"ChargeCategory": "Usage", "ServiceCategory": "Compute", "BilledCost": "40.00",
         "CommitmentDiscountId": "", "CommitmentDiscountStatus": "", "ProviderName": "AWS"},
        {"ChargeCategory": "Purchase", "ServiceCategory": "Compute", "BilledCost": "50.00",
         "CommitmentDiscountId": "c-1", "CommitmentDiscountStatus": "Used",
         "ProviderName": "AWS"},
    ]
    result = analyze(rows, DEFAULT_ELIGIBLE)
    assert result["coverage_pct"] == "60.0"
    assert result["utilization_pct"] == "100.0"


def test_ineligible_categories_stay_out_of_the_denominator():
    rows = [
        {"ChargeCategory": "Usage", "ServiceCategory": "Compute", "BilledCost": "50.00",
         "CommitmentDiscountId": "c-1", "ProviderName": "GCP", "CommitmentDiscountStatus": ""},
        {"ChargeCategory": "Usage", "ServiceCategory": "Storage", "BilledCost": "950.00",
         "CommitmentDiscountId": "", "ProviderName": "GCP", "CommitmentDiscountStatus": ""},
    ]
    result = analyze(rows, DEFAULT_ELIGIBLE)
    assert result["coverage_pct"] == "100.0"  # storage never dilutes the number
    assert Decimal(result["eligible_usage_dollars"]) == Decimal("50.00")


def test_badge_is_billing_not_estimated():
    assert analyze(sample_rows(), DEFAULT_ELIGIBLE)["badge"] == "billing"
