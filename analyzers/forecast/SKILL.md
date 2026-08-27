---
name: forecast
description: >-
  Project period-end spend from actuals to date, with the assumptions stated and every
  output badged estimated. Use when someone asks "where will we land this month", "are we
  going to blow the budget", "projected spend", "run rate", "full-month forecast". Two
  methods, both shown: run-rate (actuals to date plus recent daily average times remaining
  days) and linear trend (least-squares over the daily series). When they disagree
  materially the report says so and why: a step change makes the linear fit extrapolate
  the jump as perpetual growth and overshoot, while run-rate holds the new level flat,
  so the disagreement itself is the finding. The last day of actuals is excluded
  when partial-day data is possible, for the same reason every tool here excludes it: a
  partial day reads as a decline and drags any projection down.
---

# forecast

## Data Contract

**In:** a FOCUS CSV and the target period (`--period 2026-06`); optionally `--recent-days N` for the run-rate window (default 7) and `--include-last-day` to keep the newest day. **Out:** JSON: actuals to date, days elapsed and remaining, both projections, their spread, and a `badge: estimated` on everything projected.

## Rules

- **Two methods, disagreement surfaced.** Run-rate reacts to level shifts; trend resists noise. A spread over 10% is flagged rather than averaged away, because the divergence is information: something recently changed.
- **Only Usage projects.** One-time purchases in the actuals would project as if they recur daily.
- **Days with zero rows count as zero-spend days** in the trend, not as missing: an idle weekend is real, and dropping it inflates the projection.

## Usage

```powershell
python forecast.py --in focus.csv --period 2026-06
python -m pytest -q
```

## Non-Goals

Seasonality, driver-based modeling, and budget comparison (feed the projection to `budget-variance` if you want variance against plan).
