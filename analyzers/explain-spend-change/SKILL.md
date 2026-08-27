---
name: explain-spend-change
description: >-
  Say WHY spend moved, with ranked drivers and a residual, not just that it moved. Use
  when someone asks "why did spend go up", "what drove the increase", "explain the spike",
  "what changed between last week and this week", or after anomaly-detect flags something
  worth a meeting. Compares two windows and decomposes the net change into per-driver
  deltas along a dimension (owner, service, provider, region, resource), reporting each
  driver's dollar contribution, the share of gross movement the listed drivers explain,
  the residual, and which dimension the change concentrates on when none is specified.
  Defaults are like-for-like: omitting the baseline compares against the immediately
  preceding window of equal length, so nobody does date arithmetic. Never end the current
  window on today: the day's billing is partial and reads as a decline.
---

# explain-spend-change

## Data Contract

**In:** a FOCUS CSV, `--current-start/--current-end` (defaults: the newest complete window), optional `--baseline-start/--baseline-end` (default: the preceding window of equal length), optional `--dimension`. **Out:** JSON: net change, gross movement (sum of absolute deltas), drivers ranked by absolute dollar contribution with direction, share explained by the top drivers, residual, and, when no dimension is given, the per-dimension concentration scores with the winner named.

## Rules

- **Like-for-like by default.** The baseline is the immediately preceding window of equal length; unequal windows are compared per-day and say so.
- **Concentration is dominance, not share.** The winning dimension is the one whose top driver most towers over its second (top-1 to top-2 ratio by absolute delta). Share-of-movement scoring silently crowns the coarsest dimension, because aggregation cancels a coarse dimension's internal jitter and its top three then trivially explain everything; measured on the synthetic sample, a three-value dimension hit 100% share while the actual single-resource culprit sat at 47%. A change spread evenly across everything has no dominant driver anywhere, and the tool says that rather than inventing one.
- **The residual is always printed.** Drivers explaining 60% of a move leave 40% unexplained, and hiding that number is how a partial story ships as a complete one.
- **Both windows come from one dataset pass**, split locally, so the two windows can never disagree about what the data was.

## Usage

```powershell
python explain.py --in focus.csv
python explain.py --in focus.csv --current-start 2026-06-27 --current-end 2026-06-27 --dimension owner
python -m pytest -q
```

## Non-Goals

Forecasting, anomaly detection (upstream), and unit-price decomposition (price versus volume needs rate data this tool does not require).
