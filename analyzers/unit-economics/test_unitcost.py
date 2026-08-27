"""unit-economics tests: provenance required, mismatches are findings."""

import json
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from unitcost import load_units, unit_costs, UnitsError


def units_file(tmp_path, payload: dict) -> Path:
    p = tmp_path / "units.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def rows_for(spend: dict[str, str]) -> list[dict]:
    return [{"ChargeCategory": "Usage", "BilledCost": v,
             "x_owner_canonical": k, "Tags": "{}"} for k, v in spend.items()]


VALID = {"unit_name": "transactions", "source": "billing DB export 2026-06",
         "counts": {"Atlas": "1000", "Cascade": "500"}}


def test_missing_source_is_fatal(tmp_path):
    bad = {k: v for k, v in VALID.items() if k != "source"}
    with pytest.raises(UnitsError):
        load_units(units_file(tmp_path, bad))


def test_unquoted_count_is_fatal(tmp_path):
    bad = dict(VALID, counts={"Atlas": 1000})
    with pytest.raises(UnitsError):
        load_units(units_file(tmp_path, bad))


def test_source_echoed_verbatim(tmp_path):
    result = unit_costs(rows_for({"Atlas": "200.00"}), load_units(units_file(tmp_path, VALID)))
    assert result["units_source"] == "billing DB export 2026-06"
    assert result["unit_name"] == "transactions"


def test_cost_per_unit_math():
    result = unit_costs(rows_for({"Atlas": "200.00", "Cascade": "100.00"}), VALID)
    per = {e["key"]: e["cost_per_unit"] for e in result["per_key"]}
    assert Decimal(per["Atlas"]) == Decimal("0.200000")
    assert Decimal(per["Cascade"]) == Decimal("0.200000")
    assert Decimal(result["overall_cost_per_unit"]) == Decimal("0.200000")


def test_mismatches_are_findings_not_drops():
    result = unit_costs(rows_for({"Atlas": "200.00", "Ghost": "50.00"}), VALID)
    assert result["cost_without_units"] == ["Ghost"]
    assert result["units_without_cost"] == ["Cascade"]
    # And the overall number uses only matched keys.
    assert Decimal(result["total_cost"]) == Decimal("200.00")


def test_rising_spend_falling_unit_cost_story():
    """Spend up 20%, transactions up 100%: unit cost halves-ish; the point of the tool."""
    before = unit_costs(rows_for({"Atlas": "100.00"}),
                        dict(VALID, counts={"Atlas": "1000"}))
    after = unit_costs(rows_for({"Atlas": "120.00"}),
                       dict(VALID, counts={"Atlas": "2000"}))
    assert Decimal(after["overall_cost_per_unit"]) < Decimal(before["overall_cost_per_unit"])
