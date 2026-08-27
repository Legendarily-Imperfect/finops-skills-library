"""anomaly-detect tests: the planted spike must be found at the right granularity."""

import csv
import json
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from detect import detect

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gt():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_planted_spike_found_per_resource():
    spike = gt()["spike"]
    result = detect(sample_rows(), by="resource")
    victim_name = f"{spike['resource_n']:04d}"
    hit = [h for h in result["hits"]
           if h["series"].endswith(victim_name) and h["date"] == spike["date"]]
    assert hit, f"planted spike {spike} not among {result['hits'][:3]}"


def test_spike_is_top_hit_by_excess_dollars():
    spike = gt()["spike"]
    result = detect(sample_rows(), by="resource")
    assert result["hits"], "no hits at all"
    top = result["hits"][0]
    assert top["date"] == spike["date"] and top["series"].endswith(f"{spike['resource_n']:04d}")


def test_fleet_aggregate_would_have_missed_it():
    """Documents why granularity is the rule: day-level detection sees nothing."""
    result = detect(sample_rows(), by="day")
    assert result["hits"] == []


def test_newest_day_excluded():
    result = detect(sample_rows(), by="resource")
    assert result["newest_day_excluded"] is not None
    assert result["newest_day_excluded"] not in result["days_scanned"]


def test_threshold_is_respected():
    loose = detect(sample_rows(), by="resource", threshold=Decimal("1.5"))
    tight = detect(sample_rows(), by="resource", threshold=Decimal("10"))
    assert len(tight["hits"]) <= len(loose["hits"])


def test_short_series_skipped():
    rows = [{"ChargeCategory": "Usage", "BilledCost": "5", "Tags": "{}",
             "ResourceName": "r-1", "ChargePeriodStart": d}
            for d in ("2026-06-01", "2026-06-02")]
    assert detect(rows, by="resource")["hits"] == []
