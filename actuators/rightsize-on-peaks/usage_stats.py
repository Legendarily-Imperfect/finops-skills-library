#!/usr/bin/env python3
"""Distribution statistics and peak-based sizing for utilization series.

Size to the peak, never the average: averaging under-provisions spiky
workloads and causes incidents. Sustained demand is max(p99, max windowed
average); headroom adapts to variability so steady workloads earn thinner
margins. Every output is badged estimated and carries the stats that
produced it.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

WINDOW = 5
HEADROOM_BANDS = [(0.25, 0.25), (0.75, 0.35), (math.inf, 0.45)]  # (CoV ceiling, headroom)


def percentile_nearest_rank(values: list[float], p: float) -> float:
    """Nearest-rank percentile: no interpolation, so p99 is a sample that happened."""
    s = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(s)))
    return s[rank - 1]


def windowed_averages(values: list[float], window: int = WINDOW) -> list[float]:
    if len(values) < window:
        return [sum(values) / len(values)]
    return [sum(values[i:i + window]) / window for i in range(len(values) - window + 1)]


def stats(values: list[float], window: int = WINDOW) -> dict:
    if not values:
        raise SystemExit("rightsize-on-peaks: error: empty series")
    n = len(values)
    mean = sum(values) / n
    s = sorted(values)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    wins = windowed_averages(values, window)
    variance = sum((v - mean) ** 2 for v in values) / n
    stddev = math.sqrt(variance)
    return {
        "samples": n,
        "mean": round(mean, 2),
        "median": round(median, 2),
        "p95": round(percentile_nearest_rank(values, 95), 2),
        "p99": round(percentile_nearest_rank(values, 99), 2),
        "max_window_avg": round(max(wins), 2),
        "min_window_avg": round(min(wins), 2),
        "cov": round(stddev / mean, 3) if mean else 0.0,
    }


def recommend(values: list[float], current: float, unit: str,
              window: int = WINDOW, min_step: float = 0.10) -> dict:
    st = stats(values, window)
    demand_pct = max(st["p99"], st["max_window_avg"])
    headroom = next(h for ceil, h in HEADROOM_BANDS if st["cov"] <= ceil)
    target = current * demand_pct / 100 * (1 + headroom)

    if target >= current * (1 - min_step):
        verdict, recommended = "correctly_sized", current
    else:
        verdict, recommended = "downsize_candidate", round(target, 2)

    return {
        "badge": "estimated",
        "verdict": verdict,
        "current": current,
        "recommended": recommended,
        "unit": unit,
        "demand_pct": demand_pct,
        "headroom_pct": int(headroom * 100),
        "rule": "sized to max(p99, max_window_avg), never the average",
        "stats": st,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--series", type=Path, help="CSV with a utilization column")
    src.add_argument("--json", dest="json_series", help="JSON array of percent samples")
    ap.add_argument("--column", help="CSV column name (required with --series)")
    ap.add_argument("--current", type=float, required=True)
    ap.add_argument("--unit", default="units")
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--min-step", type=float, default=0.10)
    args = ap.parse_args()

    if args.series:
        if not args.column:
            raise SystemExit("rightsize-on-peaks: error: --column is required with --series")
        with args.series.open(encoding="utf-8-sig", newline="") as f:
            values = [float(r[args.column]) for r in csv.DictReader(f) if (r.get(args.column) or "").strip()]
    else:
        values = [float(v) for v in json.loads(args.json_series)]

    print(json.dumps(recommend(values, args.current, args.unit, args.window, args.min_step), indent=2))


if __name__ == "__main__":
    main()
