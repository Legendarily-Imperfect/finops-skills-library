"""forecast tests: flat data projects flat; step changes split the methods."""

from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from forecast import project


def rows_for(daily: dict[str, str]) -> list[dict]:
    return [{"ChargeCategory": "Usage", "BilledCost": v, "ChargePeriodStart": d}
            for d, v in daily.items()]


def flat_month(days: int, amount: str = "100.00") -> dict[str, str]:
    return {f"2026-06-{d:02d}": amount for d in range(1, days + 1)}


def test_flat_data_projects_the_flat_total():
    """15 flat days at $100 (day 15 excluded as partial) must project ~$3,000."""
    result = project(rows_for(flat_month(15)), "2026-06")
    assert result["newest_day_excluded"] == "2026-06-15"
    for key in ("run_rate_projection", "trend_projection"):
        assert abs(Decimal(result[key]) - 3000) < Decimal("1"), result[key]
    assert result["methods_disagree"] is False


def test_step_change_splits_the_methods():
    """A late step change makes the linear fit extrapolate the jump as
    perpetual growth (overshoot), while run-rate holds the new level flat.
    The disagreement, not either number, is the finding."""
    daily = {f"2026-06-{d:02d}": "50.00" for d in range(1, 11)}
    daily.update({f"2026-06-{d:02d}": "300.00" for d in range(11, 16)})
    result = project(rows_for(daily), "2026-06", recent_days=3)
    assert Decimal(result["trend_projection"]) > Decimal(result["run_rate_projection"])
    assert result["methods_disagree"] is True
    assert result["note"] is not None


def test_zero_days_count_not_dropped():
    daily = flat_month(10)
    del daily["2026-06-05"]  # an idle day: no rows at all
    result = project(rows_for(daily), "2026-06")
    with_gap = Decimal(result["run_rate_projection"])
    full = Decimal(project(rows_for(flat_month(10)), "2026-06")["run_rate_projection"])
    assert with_gap < full  # the gap lowers the projection; dropping it would not


def test_purchases_do_not_project():
    rows = rows_for(flat_month(10))
    rows.append({"ChargeCategory": "Purchase", "BilledCost": "99999.00",
                 "ChargePeriodStart": "2026-06-01"})
    result = project(rows, "2026-06")
    assert Decimal(result["actuals_to_date"]) == Decimal("900.00")  # 9 counted days


def test_everything_projected_is_badged():
    result = project(rows_for(flat_month(10)), "2026-06")
    assert result["badge"] == "estimated"


def test_empty_period_is_error():
    with pytest.raises(SystemExit):
        project(rows_for(flat_month(10)), "2026-07")
