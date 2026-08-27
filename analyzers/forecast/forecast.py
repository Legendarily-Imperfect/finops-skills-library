#!/usr/bin/env python3
"""Period-end projection from actuals: run-rate and linear trend, both shown.

Run-rate holds a new level flat; a linear fit converts a one-time step into perpetual growth and overshoots. When they
disagree materially the report says so instead of averaging the disagreement
away, because divergence is information: something recently changed.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SPREAD_FLAG_PCT = Decimal("10")


def daily_usage(rows: list[dict], period: str) -> dict[date, Decimal]:
    out: dict[date, Decimal] = {}
    for r in rows:
        if (r.get("ChargeCategory") or "").strip() != "Usage":
            continue
        raw = (r.get("ChargePeriodStart") or "")[:10]
        if raw.startswith(period):
            d = date.fromisoformat(raw)
            out[d] = out.get(d, Decimal("0")) + Decimal(r.get("BilledCost") or "0")
    return out


def project(rows: list[dict], period: str, recent_days: int = 7,
            include_last_day: bool = False) -> dict:
    series = daily_usage(rows, period)
    if not series:
        raise SystemExit(f"forecast: error: no Usage rows in period {period}")
    year, month = int(period[:4]), int(period[5:7])
    days_in_period = calendar.monthrange(year, month)[1]

    days = sorted(series)
    if not include_last_day and len(days) > 1:
        excluded = days[-1]
        days = days[:-1]
    else:
        excluded = None

    # Zero-fill: an idle day is real, and dropping it inflates the projection.
    first, last = days[0], days[-1]
    full = [(d, series.get(d, Decimal("0")))
            for d in (first + timedelta(days=i) for i in range((last - first).days + 1))]

    actuals = sum((v for _, v in full), Decimal("0"))
    elapsed = len(full)
    remaining = days_in_period - last.day

    recent = full[-recent_days:]
    recent_avg = sum((v for _, v in recent), Decimal("0")) / len(recent)
    run_rate = actuals + recent_avg * remaining

    # Least squares over day index; slope in dollars/day.
    n = Decimal(len(full))
    xs = [Decimal(i) for i in range(len(full))]
    ys = [v for _, v in full]
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denom if denom else Decimal("0")
    intercept = (sy - slope * sx) / n
    trend = actuals + sum(
        (max(Decimal("0"), intercept + slope * Decimal(len(full) + i)) for i in range(remaining)),
        Decimal("0"))

    lo, hi = sorted([run_rate, trend])
    spread_pct = (hi - lo) / hi * 100 if hi else Decimal("0")
    return {
        "badge": "estimated",
        "period": period,
        "actuals_to_date": format(actuals, "f"),
        "days_elapsed": elapsed,
        "days_remaining": remaining,
        "newest_day_excluded": excluded.isoformat() if excluded else None,
        "run_rate_projection": format(run_rate, ".2f"),
        "trend_projection": format(trend, ".2f"),
        "spread_pct": format(spread_pct, ".1f"),
        "methods_disagree": bool(spread_pct > SPREAD_FLAG_PCT),
        "note": ("methods disagree beyond 10%: something recently changed. A step "
                 "change makes the linear fit extrapolate the jump as perpetual "
                 "growth (overshoot) while run-rate holds the new level flat; "
                 "investigate the change before quoting either number"
                 if spread_pct > SPREAD_FLAG_PCT else None),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--period", required=True, help="YYYY-MM")
    ap.add_argument("--recent-days", type=int, default=7)
    ap.add_argument("--include-last-day", action="store_true")
    args = ap.parse_args()
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(project(rows, args.period, args.recent_days,
                             args.include_last_day), indent=2))


if __name__ == "__main__":
    main()
