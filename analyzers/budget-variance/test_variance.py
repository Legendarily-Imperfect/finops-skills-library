"""budget-variance tests: validations are fatal, ranking is by dollars."""

import json
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from variance import load_budgets, variance, BudgetError


def write_budgets(tmp_path, content: str) -> Path:
    p = tmp_path / "budgets.json"
    p.write_text(content, encoding="utf-8")
    return p


def rows_for(spend: dict[str, str]) -> list[dict]:
    return [{"ChargeCategory": "Usage", "BilledCost": v,
             "x_owner_canonical": k, "Tags": "{}"} for k, v in spend.items()]


def test_valid_file_loads(tmp_path):
    p = write_budgets(tmp_path, '{"budgets": {"Atlas": "5000.00"}}')
    assert load_budgets(p)["budgets"]["Atlas"] == "5000.00"


def test_unquoted_amount_is_fatal(tmp_path):
    p = write_budgets(tmp_path, '{"budgets": {"Atlas": 5000.00}}')
    with pytest.raises(BudgetError):
        load_budgets(p)


def test_duplicate_owner_is_fatal(tmp_path):
    p = write_budgets(tmp_path, '{"budgets": {"Atlas": "1.00", "Atlas": "2.00"}}')
    with pytest.raises(BudgetError):
        load_budgets(p)


def test_malformed_amount_is_fatal(tmp_path):
    for bad in ('"$5,000.00"', '"-100"', '"5 000"'):
        p = write_budgets(tmp_path, f'{{"budgets": {{"Atlas": {bad}}}}}')
        with pytest.raises(BudgetError):
            load_budgets(p)


def test_empty_budgets_is_fatal(tmp_path):
    p = write_budgets(tmp_path, '{"budgets": {}}')
    with pytest.raises(BudgetError):
        load_budgets(p)


def test_ranked_by_dollars_not_percent():
    """The $40K overrun outranks the 300% overrun on a $12 budget."""
    result = variance(
        rows_for({"Big": "140000.00", "Tiny": "48.00"}),
        {"Big": "100000.00", "Tiny": "12.00"})
    assert result["by_owner"][0]["owner"] == "Big"
    assert Decimal(result["by_owner"][0]["variance"]) == Decimal("40000.00")


def test_statuses():
    result = variance(
        rows_for({"Over": "150.00", "Under": "50.00", "Unbudgeted": "10.00"}),
        {"Over": "100.00", "Under": "100.00", "Dormant": "500.00"})
    status = {e["owner"]: e["status"] for e in result["by_owner"]}
    assert status == {"Over": "over", "Under": "under",
                      "Unbudgeted": "no_budget", "Dormant": "no_spend"}


def test_totals_are_decimal_exact():
    result = variance(rows_for({"A": "0.10", "B": "0.20"}), {"A": "0.15", "B": "0.15"})
    assert result["totals"]["actual"] == "0.30"
    assert result["totals"]["variance"] == "0.00"
