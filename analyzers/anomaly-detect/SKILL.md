---
name: anomaly-detect
description: >-
  Flag days and resources that break from their own baseline, at the granularity where
  anomalies actually live. Use when someone asks "did anything spike", "why was yesterday
  expensive", "watch for anomalies", "any unusual spend", or a daily total looks off. The
  detection rule is deliberately simple and stated: a period is anomalous when it exceeds
  1.5x its own series' average. The granularity rule is the real content: a single
  resource quadrupling for a day barely moves a fleet-wide total, so detection runs
  per-series (per resource, owner, or service), and the fleet view is a roll-up of
  per-series hits, not a screen on the aggregate. Aggregate-only monitoring is how a
  four-times spike hides inside a two-percent day.
---

# anomaly-detect

## Data Contract

**In:** a FOCUS CSV and `--by resource|owner|service|day` (default `resource`). **Out:** JSON: hits ranked by excess dollars (actual minus baseline), each with the series key, date, actual, series average, and multiple; plus the window scanned and the rule applied.

## Rules

- **Per-series baselines.** Each series is compared to its own average, not the fleet's: a $9/day resource spiking to $36 is a hit even while the fleet moves 1%.
- **Excess dollars rank the hits.** A 10x spike on pennies matters less than a 2x spike on thousands; the multiple is reported, the dollars sort.
- **The current day is excluded** when the data includes it, because partial days read as declines and their spikes are understated. Stated in the output.
- **Threshold is a parameter with a stated default** (1.5x). Tightening it is a decision about noise tolerance, not a code change.

## Usage

```powershell
python detect.py --in focus.csv --by resource
python detect.py --in focus.csv --by owner --threshold 2.0
python -m pytest -q
```

## Non-Goals

Root cause (that is `explain-spend-change`: run it on any hit worth a meeting), seasonality modeling, and alert delivery.
