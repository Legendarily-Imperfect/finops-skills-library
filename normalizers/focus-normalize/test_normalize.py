"""Tests for focus-normalize: detection, preservation, money discipline, tags."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from normalize import FOCUS_COLUMNS, detect_mapping, load_mappings, normalize_rows, plain_money, NormalizeError

SAMPLE = Path(__file__).parents[2] / "synthetic-data" / "sample" / "billing.csv"
MAPPINGS = load_mappings()


def rows_from(header, *values):
    return [dict(zip(header, v)) for v in values]


# ---- detection -------------------------------------------------------------

def test_detects_each_shipped_mapping_uniquely():
    for name, m in MAPPINGS.items():
        assert detect_mapping(list(m["fingerprint"]) + ["some_random_col"], MAPPINGS) == name


def test_detection_failure_names_fingerprints():
    with pytest.raises(NormalizeError):
        detect_mapping(["nothing", "recognizable"], MAPPINGS)


# ---- money -----------------------------------------------------------------

def test_money_renders_plain():
    assert plain_money("1E-7", 2, "BilledCost") == "0.0000001"
    assert plain_money("  3.50 ", 2, "BilledCost") == "3.50"
    assert plain_money("", 2, "BilledCost") == ""


def test_money_garbage_is_named_error():
    with pytest.raises(NormalizeError):
        plain_money("N/A", 7, "BilledCost")


# ---- gcp labels array ------------------------------------------------------

def test_gcp_labels_array_becomes_tag_object():
    m = MAPPINGS["gcp_billing"]
    header = list(m["columns"]) + ["labels"]
    row = {c: "" for c in header}
    row.update({"cost": "1.5", "labels": '[{"key":"owner","value":"Atlas"},{"key":"env","value":"prod"}]'})
    out = normalize_rows([row], header, m)
    assert json.loads(out[0]["Tags"]) == {"owner": "Atlas", "env": "prod"}
    assert out[0]["ProviderName"] == "GCP"


# ---- aws tag prefix folding ------------------------------------------------

def test_aws_tag_prefix_folds_and_is_not_duplicated_as_x_src():
    m = MAPPINGS["aws_cur2"]
    header = list(m["columns"]) + ["resource_tags_user_owner", "mystery_column"]
    row = {c: "" for c in header}
    row.update({"line_item_unblended_cost": "2.00", "resource_tags_user_owner": "Cascade",
                "mystery_column": "kept"})
    out = normalize_rows([row], header, m)
    assert json.loads(out[0]["Tags"]) == {"owner": "Cascade"}
    assert out[0]["x_src_mystery_column"] == "kept"
    assert "x_src_resource_tags_user_owner" not in out[0]


# ---- missing mapped column aborts ------------------------------------------

def test_missing_mapped_column_refuses_all_rows():
    m = MAPPINGS["azure_cost"]
    header = ["Date", "MeterCategory"]  # far from complete
    with pytest.raises(NormalizeError):
        normalize_rows(rows_from(header, ["2026-06-01", "Compute"]), header, m)


# ---- end to end on the synthetic sample ------------------------------------

def test_cli_passthrough_on_synthetic_sample(tmp_path):
    out = tmp_path / "focus.csv"
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "normalize.py"),
         "--in", str(SAMPLE), "--out", str(out)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "focus_passthrough" in proc.stdout
    with out.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with SAMPLE.open(encoding="utf-8") as f:
        src_rows = list(csv.DictReader(f))
    assert len(rows) == len(src_rows)
    # Totals survive the round trip to the cent.
    from decimal import Decimal
    assert sum(Decimal(r["BilledCost"]) for r in rows) == sum(Decimal(r["BilledCost"]) for r in src_rows)
    # Output leads with the FOCUS columns in canonical order.
    assert list(rows[0].keys())[: len(FOCUS_COLUMNS)] == FOCUS_COLUMNS
