"""waste-classify tests: planted defects land in the right classes, badges honest."""

import csv
import json
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from classify import classify, DEFAULT_CONFIG

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gt():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def result():
    return classify(sample_rows(), DEFAULT_CONFIG)


def test_planted_idle_resources_all_found():
    idle_names = {r["name"] for r in result()["classes"]["idle"]["resources"]}
    for n in gt()["idle_resource_ns"]:
        assert any(name.endswith(f"{n:04d}") for name in idle_names), f"idle {n} missed"


def test_planted_unused_commitments_found_with_full_recovery():
    cls = result()["classes"]["unused_commitment"]
    assert {r["name"] for r in cls["resources"]} == {c["id"] for c in gt()["unused_commitments"]}
    assert cls["recovery_rate_assumed"] == "1.0"
    assert cls["recoverable_dollars"] == format(Decimal(cls["billed_dollars"]), ".2f")


def test_old_generation_found_where_not_idle():
    """First-match rule: an idle old-gen resource classifies as idle, so only
    old-gen resources that are NOT also idle appear here."""
    r = result()
    truth = gt()
    idle_ns = set(truth["idle_resource_ns"])
    expected = {n for n in truth["old_generation_resource_ns"] if n not in idle_ns}
    found = {name for name in
             (x["name"] for x in r["classes"].get("old_generation", {}).get("resources", []))}
    for n in expected:
        assert any(name.endswith(f"{n:04d}") for name in found), f"old-gen {n} missed"


def test_badges_are_honest():
    r = result()
    for cls in r["classes"].values():
        assert cls["billed_badge"] == "billing"
        assert cls["recoverable_badge"] == "estimated"
        assert Decimal(cls["recoverable_dollars"]) <= Decimal(cls["billed_dollars"]) + Decimal("0.01")
    assert "estimated" in r["total_recoverable_badge"]


def test_recovery_rate_override_moves_the_estimate():
    tight = classify(sample_rows(), {**DEFAULT_CONFIG,
                                     "recovery_rates": {**DEFAULT_CONFIG["recovery_rates"],
                                                        "idle": "0.1"}})
    loose = result()
    assert (Decimal(tight["classes"]["idle"]["recoverable_dollars"])
            < Decimal(loose["classes"]["idle"]["recoverable_dollars"]))


def test_one_class_per_resource():
    r = result()
    seen: set[str] = set()
    for cls in r["classes"].values():
        for res in cls["resources"]:
            assert res["name"] not in seen, f"{res['name']} double-counted"
            seen.add(res["name"])
