#!/usr/bin/env python3
"""Per-series spend anomaly detection: each series against its own baseline.

A single resource quadrupling for a day barely moves a fleet total, so
detection runs per series and the fleet view is a roll-up of per-series hits.
Hits rank by excess dollars: a 10x spike on pennies matters less than a 2x
spike on thousands.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

DEFAULT_THRESHOLD = Decimal("1.5")


def series_key(row: dict, by: str) -> str:
    if by == "resource":
        return row.get("ResourceName") or row.get("ResourceId") or "(no-resource)"
    if by == "owner":
        if (c := (row.get("x_owner_canonical") or "").strip()):
            return c
        try:
            return json.loads(row.get("Tags") or "{}").get("owner") or "(untagged)"
        except json.JSONDecodeError:
            return "(untagged)"
    if by == "service":
        return row.get("ServiceName") or "(no-service)"
    if by == "day":
        return "(all)"
    raise SystemExit(f"anomaly-detect: error: unknown --by {by!r}")


def detect(rows: list[dict], by: str = "resource",
           threshold: Decimal = DEFAULT_THRESHOLD) -> dict:
    daily: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for r in rows:
        if (r.get("ChargeCategory") or "").strip() != "Usage":
            continue
        day = (r.get("ChargePeriodStart") or "")[:10]
        if day:
            daily[series_key(r, by)][day] += Decimal(r.get("BilledCost") or "0")

    all_days = sorted({d for series in daily.values() for d in series})
    # Exclude the newest day when more than one exists: partial days lie.
    scanned = all_days[:-1] if len(all_days) > 1 else all_days
    excluded_day = all_days[-1] if len(all_days) > 1 else None

    hits = []
    for key, series in daily.items():
        points = {d: v for d, v in series.items() if d in set(scanned)}
        if len(points) < 3:  # a baseline of two points is a coin flip
            continue
        avg = sum(points.values(), Decimal("0")) / len(points)
        if avg == 0:
            continue
        for day, value in points.items():
            if value > avg * threshold:
                hits.append({
                    "series": key, "date": day,
                    "actual": format(value, "f"),
                    "series_avg": format(avg, ".6f"),
                    "multiple": format(value / avg, ".2f"),
                    "excess_dollars": format(value - avg, "f"),
                })
    hits.sort(key=lambda h: Decimal(h["excess_dollars"]), reverse=True)
    return {
        "by": by,
        "rule": f"period > {threshold}x its own series average",
        "days_scanned": scanned,
        "newest_day_excluded": excluded_day,
        "hits": hits,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--by", default="resource", choices=["resource", "owner", "service", "day"])
    ap.add_argument("--threshold", default="1.5")
    args = ap.parse_args()
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(detect(rows, args.by, Decimal(args.threshold)), indent=2))


if __name__ == "__main__":
    main()
