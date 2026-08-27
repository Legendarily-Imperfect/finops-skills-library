"""tag-reconcile tests, driven by the synthetic sample's ground truth."""

import csv
import json
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from reconcile import load_map, reconcile, resolve, UNTAGGED

SAMPLE_DIR = Path(__file__).parents[2] / "synthetic-data" / "sample"
CANONICAL = ["Atlas", "Borealis", "Cascade", "Delta", "Ember", "Foxtrot", "Grove", "Harbor"]


def make_map(tmp_path, aliases=None, allowlist=None):
    p = tmp_path / "owner-map.json"
    p.write_text(json.dumps({
        "tag_key": "owner", "canonical": CANONICAL,
        "aliases": aliases or {}, "allowlist": allowlist or [],
    }), encoding="utf-8")
    return load_map(p)


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ground_truth():
    return json.loads((SAMPLE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_resolve_classes(tmp_path):
    m = make_map(tmp_path, aliases={"delta-team": "Delta"})
    assert resolve("Atlas", m) == ("Atlas", "ok")
    assert resolve("ATLAS", m) == ("Atlas", "variant")
    assert resolve("Cascade ", m) == ("Cascade", "variant")
    assert resolve("delta-team", m) == ("Delta", "alias")
    assert resolve("mystery", m) == ("mystery", "unknown")
    assert resolve(None, m) == (UNTAGGED, "untagged")


def test_typos_stay_unknown_without_alias(tmp_path):
    """Never guess: 'cascasde' must NOT auto-match Cascade."""
    m = make_map(tmp_path)
    assert resolve("cascasde", m) == ("cascasde", "unknown")


def test_full_recovery_with_ground_truth_aliases(tmp_path):
    gt = ground_truth()
    aliases = {v["written"]: v["canonical"] for v in gt["tag_variants"]
               if v["written"].strip().lower() not in {c.lower() for c in CANONICAL}}
    m = make_map(tmp_path, aliases=aliases)
    rows, report = reconcile(sample_rows(), m)
    classes = {d["class"] for d in report["defects"]}
    assert "unknown" not in classes, report["defects"]
    # Only untagged remains unrecoverable, exactly as planted.
    untagged = [d for d in report["defects"] if d["class"] == "untagged"]
    assert untagged, "planted untagged resources must appear"


def test_by_owner_totals_match_ground_truth(tmp_path):
    """After reconciliation, canonical-owner totals equal the answer key."""
    gt = ground_truth()
    aliases = {v["written"]: v["canonical"] for v in gt["tag_variants"]}
    m = make_map(tmp_path, aliases=aliases)
    rows, _ = reconcile(sample_rows(), m)
    totals = {}
    for r in rows:
        if r["ChargeCategory"] != "Usage":
            continue
        k = r["x_owner_canonical"]
        totals[k] = totals.get(k, Decimal("0")) + Decimal(r["BilledCost"])
    expected = gt["totals"]["by_owner"]
    assert {k: format(v, "f") for k, v in totals.items()} == expected


def test_defects_ranked_by_dollars(tmp_path):
    m = make_map(tmp_path)
    _, report = reconcile(sample_rows(), m)
    amounts = [Decimal(d["dollars"]) for d in report["defects"]]
    assert amounts == sorted(amounts, reverse=True)


def test_allowlist_silences_known_divergence(tmp_path):
    gt = ground_truth()
    unknown_written = [v["written"] for v in gt["tag_variants"]][0]
    m_without = make_map(tmp_path)
    _, before = reconcile(sample_rows(), m_without)
    m_with = make_map(tmp_path, allowlist=[unknown_written])
    _, after = reconcile(sample_rows(), m_with)
    assert len(after["defects"]) < len(before["defects"])
