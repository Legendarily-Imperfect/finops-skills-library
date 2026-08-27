---
name: otel-token-pull
description: >-
  Pull per-user LLM token usage from OTEL metrics in a Prometheus-compatible store,
  correctly, which almost nobody does on the first try. Use when someone says "token
  usage by user", "who is using the AI", "pull the LLM telemetry", "Copilot/Claude usage
  numbers", "tokens per day". Four traps, each with the measurement or mechanism that
  earned it: token metrics are DELTA temporality despite counter-style names, so
  sum_over_time is correct and rate()/increase() overstated a 24-hour total by more than
  13x while looking plausible; metric and label names contain dots, so a bare selector
  parses fine and returns zero series, which reads as a quiet week; a point at T covers
  (T-1h, T], so a daily window's first point is 01:00, not midnight, or you silently get
  an extra hour-wide bucket; and Prometheus omits empty buckets, so buckets are pre-zeroed
  or a gap in the chart reads as an outage. Model labels arrive in several spellings per
  model; normalization keeps the raw label beside the family.
---

# otel-token-pull

## Data Contract

**In:** metric name, a window (`--days` or `--hours`, capped at 7 days), optional user filter; `--emit-promql` prints the query, live mode queries a Prometheus-compatible `query_range` endpoint (`--endpoint`). **Out:** CSV: `bucket_start, user, model_raw, model_family, tokens`, every bucket present (pre-zeroed), hourly step summed client-side into the requested grain.

## The Rules

- **`sum_over_time`, never `rate` or `increase`.** Delta temporality: each sample is what accrued in that interval; the series is not monotonic. Measured error from `increase()`: more than 13x overstated on a day. Done right, the store agrees with the gateway's own ledger to under 1%.
- **Quote the dotted names.** `__name__` selector for the metric, quoted label keys. The unquoted form parses and returns zero series: the easiest way to ship this broken and have it look like a quiet week.
- **Hourly step, `[1h]` window, summed client-side.** A daily step needs the range to end on a future midnight or the last bucket silently becomes a trailing 24 hours labeled as a calendar day.
- **A point at T covers `(T-1h, T]`.** The first point of a day is its 01:00; starting at midnight returns an extra bucket one hour wide.
- **Pre-zero every bucket.** An idle hour is a zero, not a gap; without pre-zeroing, "no usage" and "no such bucket" are indistinguishable.
- **Normalize model labels into a family and keep `model_raw` beside it.** One model arrives spelled several ways; grouping on the raw label scatters it across rows and, once prices attach, across prices.

## Usage

```powershell
python otel_pull.py --metric claude_code.token.usage --days 7 --emit-promql
python otel_pull.py --metric claude_code.token.usage --days 7 --endpoint http://prometheus:9090 --out tokens.csv
python -m pytest -q
```

## Non-Goals

Dollars (pair with your rates; see `ai-spend` for why blended rates need a caveat), collector deployment, and any store write.
