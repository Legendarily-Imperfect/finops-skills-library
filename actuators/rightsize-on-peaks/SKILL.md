---
name: rightsize-on-peaks
description: >-
  Size a workload to its peaks, never its average, and show the distribution that justifies
  the number. Use when someone asks "can we downsize X", "is this VM oversized", "what
  should this instance be", "rightsizing recommendations", "how much headroom does X need",
  or hands you a utilization series. The rule this skill exists for: averaging
  under-provisions spiky workloads and causes incidents, because a workload at 20% average
  with 95% peaks is not an 80% savings candidate, it is a correctly sized spiky workload.
  Six distribution statistics with windowed-average semantics, then a target sized to the
  peak with variability-adaptive headroom: steadier workloads earn thinner headroom. Every
  recommendation is badged estimated, and the stats that produced it ride along, because a
  resize proposal that cannot show its distribution is an incident proposal.
---

# rightsize-on-peaks

## Data Contract

**In:** a utilization series (CSV column or JSON array of percent samples, 0 to 100) and the current capacity in any unit you choose. **Out:** the six statistics, a variability class, a recommended capacity in the same unit, badged `estimated`, with the stats inline.

## The Six Statistics (Windowed-Average Semantics)

`mean`, `median`, `p95`, `p99`, `max_window_avg`, `min_window_avg`. The windowed pair averages over a sliding window (default 5 samples) before taking max/min, because a single-sample max is noise and a windowed max is sustained demand. Percentiles use nearest-rank on the raw samples.

## The Sizing Rule

1. Demand is `max(p99, max_window_avg)`: sustained peak, not instantaneous blip, not average.
2. Headroom by coefficient of variation (CoV = stddev/mean): under 0.25 gets 25%, 0.25 to 0.75 gets 35%, above gets 45%. Spiky workloads earn more room, steady ones less.
3. `recommended = current x demand_pct / 100 x (1 + headroom)`, floored at a `--min-step` fraction of current so trivial resizes are not proposed.
4. A workload whose demand is within headroom of current is `correctly_sized`, and the tool says so rather than inventing a change.

## Usage

```powershell
python usage_stats.py --series cpu.csv --column cpu_pct --current 8 --unit vCPU
python usage_stats.py --json "[12,14,9,88,91,13]" --current 16 --unit vCPU
python -m pytest -q
```

## Non-Goals

Fetching the metrics (that is a collector's or your monitoring stack's job), cost math (pair the resize with your pricing), and any write. Recommendations are proposals with evidence, nothing more.
