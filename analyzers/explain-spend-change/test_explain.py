"""explain-spend-change tests: the planted spike's owner must surface as the driver."""

import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from explain import decompose, concentration, data_window

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gt():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def spike_windows():
    d = date.fromisoformat(gt()["spike"]["date"])
    return (d, d), (date.fromordinal(d.toordinal() - 1), date.fromordinal(d.toordinal() - 1))


def test_spike_resource_is_top_driver():
    cur, base = spike_windows()
    result = decompose(sample_rows(), cur, base, "resource")
    top = result["drivers"][0]
    assert top["key"].endswith(f"{gt()['spike']['resource_n']:04d}")
    assert top["direction"] == "up"


def test_spike_service_is_top_service_driver():
    cur, base = spike_windows()
    result = decompose(sample_rows(), cur, base, "service")
    assert result["drivers"][0]["key"] == gt()["spike"]["service"]


def test_residual_always_present_and_consistent():
    cur, base = spike_windows()
    result = decompose(sample_rows(), cur, base, "owner")
    gross = Decimal(result["gross_movement"])
    explained_share = Decimal(result["share_explained_pct"])
    residual = Decimal(result["residual"])
    assert residual >= 0
    recomputed = (gross - residual) / gross * 100 if gross else Decimal("0")
    assert abs(recomputed - explained_share) < Decimal("0.1")


def test_concentration_prefers_resource_for_single_resource_spike():
    cur, base = spike_windows()
    conc = concentration(sample_rows(), cur, base)
    assert conc["most_concentrated"] == "resource"


def test_unequal_windows_compare_per_day():
    rows = sample_rows()
    lo, hi = data_window(rows)
    result = decompose(rows, (hi, hi), (lo, date.fromordinal(lo.toordinal() + 2)), "provider")
    assert result["unit"] == "dollars_per_day"


def test_equal_windows_report_dollars():
    cur, base = spike_windows()
    result = decompose(sample_rows(), cur, base, "provider")
    assert result["unit"] == "dollars"
