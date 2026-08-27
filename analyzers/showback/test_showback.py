"""showback tests: allocation matches ground truth once tags are reconciled."""

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from showback import showback, owner_of, UNTAGGED

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"
sys.path.insert(0, str(Path(__file__).parents[2] / "normalizers" / "tag-reconcile"))
from reconcile import load_map, reconcile  # noqa: E402


def reconciled_rows(tmp_path):
    gt = json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    map_path = tmp_path / "m.json"
    map_path.write_text(json.dumps({
        "tag_key": "owner",
        "canonical": sorted({v["canonical"] for v in gt["tag_variants"]}
                            | set(gt["totals"]["by_owner"]) - {UNTAGGED}),
        "aliases": {v["written"]: v["canonical"] for v in gt["tag_variants"]},
    }), encoding="utf-8")
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows, _ = reconcile(rows, load_map(map_path))
    return rows, gt


def test_matches_ground_truth_after_reconcile(tmp_path):
    rows, gt = reconciled_rows(tmp_path)
    result = showback(rows)
    ours = {o["owner"]: o["dollars"] for o in result["owners"]}
    assert ours == gt["totals"]["by_owner"]


def test_untagged_is_a_named_line_never_spread(tmp_path):
    rows, gt = reconciled_rows(tmp_path)
    result = showback(rows)
    assert any(o["owner"] == UNTAGGED for o in result["owners"])
    assert result["owners"] == sorted(result["owners"],
                                      key=lambda o: Decimal(o["dollars"]), reverse=True)


def test_non_usage_excluded_not_allocated(tmp_path):
    rows, _ = reconciled_rows(tmp_path)
    result = showback(rows)
    assert "Purchase" in result["excluded_categories"]
    assert Decimal(result["excluded_categories"]["Purchase"]) > 0


def test_shares_sum_to_100(tmp_path):
    rows, _ = reconciled_rows(tmp_path)
    result = showback(rows)
    total = sum(Decimal(o["share_pct"]) for o in result["owners"])
    assert abs(total - 100) < Decimal("0.5")


def test_owner_falls_back_to_raw_tag_without_reconcile():
    row = {"Tags": '{"owner": "ATLAS"}'}
    assert owner_of(row) == "ATLAS"  # verbatim: the doc says run tag-reconcile first
    row["x_owner_canonical"] = "Atlas"
    assert owner_of(row) == "Atlas"
