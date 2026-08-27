"""spend-tieout tests: exact tie against ground truth, causes actually explain gaps."""

import csv
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tieout import profile, compare

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gt():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_dataset_ties_to_ground_truth_exactly():
    prof = profile(sample_rows())
    assert format(prof["total"], "f") == gt()["totals"]["grand_total"]


def test_cli_tie_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "tieout.py"),
         "--focus", str(SAMPLE_DIR / "billing.csv"),
         "--source-total", gt()["totals"]["grand_total"], "--source-name", "answer-key"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
    assert '"verdict": "tie"' in proc.stdout


def test_gap_names_category_cause():
    """Remove the Purchase rows (unused commitments) from the source total:
    the gap must be explained by the Purchase category, flagged as such."""
    prof = profile(sample_rows())
    purchase = Decimal(prof["by_category"]["Purchase"])
    source_without_purchases = prof["total"] - purchase
    result = compare("invoice", source_without_purchases, "dataset", prof["total"],
                     Decimal("0.01"), prof)
    assert result["verdict"] == "gap"
    hits = [c for c in result.get("candidate_causes", [])
            if c.get("explains_gap") and "Purchase" in c["cause"]]
    assert hits, result["candidate_causes"]


def test_gap_names_provider_scope_cause():
    prof = profile(sample_rows())
    gcp = Decimal(prof["by_provider"]["GCP"])
    result = compare("invoice", prof["total"] - gcp, "dataset", prof["total"],
                     Decimal("0.01"), prof)
    hits = [c for c in result.get("candidate_causes", [])
            if c.get("explains_gap") and "GCP" in c["cause"]]
    assert hits


def test_window_always_reported_on_gap():
    prof = profile(sample_rows())
    result = compare("invoice", prof["total"] - Decimal("123.45"), "dataset",
                     prof["total"], Decimal("0.01"), prof)
    assert any("calendar vs invoice" in c["cause"] for c in result["candidate_causes"])


def test_mixed_currency_red_flag(tmp_path):
    rows = sample_rows()
    rows[0]["BillingCurrency"] = "EUR"
    prof = profile(rows)
    result = compare("a", prof["total"], "b", prof["total"], Decimal("0.01"), prof)
    assert "red_flag" in result and "EUR" in result["red_flag"]


def test_tolerance_is_respected():
    prof = profile(sample_rows())
    near = prof["total"] - Decimal("5")
    tight = compare("s", near, "d", prof["total"], Decimal("0.01"), prof)
    loose = compare("s", near, "d", prof["total"], Decimal("10"), prof)
    assert tight["verdict"] == "gap" and loose["verdict"] == "tie"
