"""parity-check tests, including the pattern used on itself against the sample."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from parity import locate, load_json, diff

SAMPLE_GT = Path(__file__).parents[2] / "synthetic-data" / "sample" / "ground_truth.json"


def test_identical_dicts_no_problems():
    d = {"a": 1, "nested": {"x": "y"}}
    assert diff(d, json.loads(json.dumps(d))) == []


def test_diff_names_all_three_kinds():
    ours = {"only_ours": 1, "both": 2, "nested": {"same": 1, "differs": "a"}}
    theirs = {"only_theirs": 3, "both": 2, "nested": {"same": 1, "differs": "b"}}
    problems = diff(ours, theirs)
    assert any(p.startswith("only in ours: only_ours") for p in problems)
    assert any(p.startswith("only in theirs: only_theirs") for p in problems)
    assert any("value differs at nested.differs" in p for p in problems)
    assert len(problems) == 3


def test_allowlist_silences_key_and_children():
    ours = {"legacy": {"a": 1, "b": 2}, "live": 1}
    theirs = {"legacy": {"a": 9}, "live": 2}
    problems = diff(ours, theirs, allowlist=["legacy"])
    assert problems == ["value differs at live: ours 1, theirs 2"]


def test_locate_absent_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("PEER_TEST_REPO", raising=False)
    assert locate("PEER_TEST_REPO", str(tmp_path / "nope")) is None


def test_locate_env_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PEER_TEST_REPO", str(tmp_path))
    assert locate("PEER_TEST_REPO", "c:/definitely/absent") == tmp_path


# --- the pattern applied to this library itself -----------------------------

PEER = SAMPLE_GT if SAMPLE_GT.exists() else None


@pytest.mark.skipif(PEER is None, reason="synthetic sample absent")
def test_sample_owner_totals_parity_with_ground_truth():
    """Self-referential worked example: the sample's by-owner totals recomputed
    from the CSV must match the ground truth. This is the exact shape a buyer
    copies to keep their fork matching their environment."""
    import csv
    from decimal import Decimal
    gt = load_json(PEER)
    totals: dict = {}
    with (PEER.parent / "billing.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["ChargeCategory"] != "Usage":
                continue
            tags = json.loads(r["Tags"])
            written = tags.get("owner")
            canonical = next((v["canonical"] for v in gt["tag_variants"]
                              if v["written"] == written), written) if written else "(untagged)"
            totals[canonical] = totals.get(canonical, Decimal("0")) + Decimal(r["BilledCost"])
    ours = {k: format(v, "f") for k, v in totals.items()}
    problems = diff(ours, gt["totals"]["by_owner"])
    assert not problems, "\n".join(problems)
