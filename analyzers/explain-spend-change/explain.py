#!/usr/bin/env python3
"""Decompose a spend change into ranked drivers along the dimension that explains it.

Like-for-like by default: the baseline is the immediately preceding window of
equal length. The residual is always printed, because drivers explaining 60%
of a move leave 40% unexplained and hiding that ships a partial story as a
complete one. Both windows come from one pass over one dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

DIMENSIONS = ["owner", "service", "provider", "region", "resource"]
TOP_N = 8


def dim_value(row: dict, dim: str) -> str:
    if dim == "owner":
        if (c := (row.get("x_owner_canonical") or "").strip()):
            return c
        try:
            return json.loads(row.get("Tags") or "{}").get("owner") or "(untagged)"
        except json.JSONDecodeError:
            return "(untagged)"
    return {
        "service": row.get("ServiceName"),
        "provider": row.get("ProviderName"),
        "region": row.get("RegionId"),
        "resource": row.get("ResourceName") or row.get("ResourceId"),
    }.get(dim) or f"(no-{dim})"


def window_totals(rows: list[dict], start: date, end: date, dim: str) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        if (r.get("ChargeCategory") or "").strip() != "Usage":
            continue
        day_raw = (r.get("ChargePeriodStart") or "")[:10]
        if not day_raw:
            continue
        day = date.fromisoformat(day_raw)
        if start <= day <= end:
            out[dim_value(r, dim)] += Decimal(r.get("BilledCost") or "0")
    return out


def decompose(rows: list[dict], cur: tuple[date, date], base: tuple[date, date],
              dim: str) -> dict:
    cur_days = (cur[1] - cur[0]).days + 1
    base_days = (base[1] - base[0]).days + 1
    per_day = cur_days != base_days  # unequal windows compare per-day and say so

    a = window_totals(rows, base[0], base[1], dim)
    b = window_totals(rows, cur[0], cur[1], dim)
    if per_day:
        a = {k: v / base_days for k, v in a.items()}
        b = {k: v / cur_days for k, v in b.items()}

    deltas = {k: b.get(k, Decimal("0")) - a.get(k, Decimal("0"))
              for k in set(a) | set(b)}
    net = sum(deltas.values(), Decimal("0"))
    gross = sum((abs(v) for v in deltas.values()), Decimal("0"))
    ranked = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)
    drivers = [{"key": k, "delta": format(v, "f"),
                "direction": "up" if v > 0 else "down"}
               for k, v in ranked[:TOP_N] if v != 0]
    explained = sum((abs(v) for _, v in ranked[:TOP_N]), Decimal("0"))
    return {
        "dimension": dim,
        "unit": "dollars_per_day" if per_day else "dollars",
        "net_change": format(net, "f"),
        "gross_movement": format(gross, "f"),
        "drivers": drivers,
        "share_explained_pct": format(explained / gross * 100, ".1f") if gross else "0.0",
        "residual": format(gross - explained, "f"),
    }


def concentration(rows: list[dict], cur, base) -> dict:
    """Which dimension's top driver most towers over its peers (top1/top2 ratio).

    Share-of-movement scoring silently crowns the coarsest dimension: a
    three-value dimension aggregates away its internal jitter (cancellation
    shrinks its gross), so its top three trivially explain ~100%. Dominance
    measures what a story actually is: one driver standing out. A dimension
    with fewer than two moving keys offers no contrast and scores zero.
    """
    scores = {}
    for dim in DIMENSIONS:
        d = decompose(rows, cur, base, dim)
        magnitudes = sorted((abs(Decimal(x["delta"])) for x in d["drivers"]), reverse=True)
        if len(magnitudes) < 2 or magnitudes[1] == 0:
            scores[dim] = "0.0"
        else:
            scores[dim] = format(magnitudes[0] / magnitudes[1], ".2f")
    winner = max(scores, key=lambda k: Decimal(scores[k]))
    return {"metric": "dominance = top driver / second driver, by absolute delta",
            "scores": scores, "most_concentrated": winner}


def data_window(rows: list[dict]) -> tuple[date, date]:
    days = sorted({(r.get("ChargePeriodStart") or "")[:10]
                   for r in rows if (r.get("ChargePeriodStart") or "").strip()})
    return date.fromisoformat(days[0]), date.fromisoformat(days[-1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--current-start"); ap.add_argument("--current-end")
    ap.add_argument("--baseline-start"); ap.add_argument("--baseline-end")
    ap.add_argument("--dimension", choices=DIMENSIONS)
    args = ap.parse_args()

    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    lo, hi = data_window(rows)

    if args.current_start and args.current_end:
        cur = (date.fromisoformat(args.current_start), date.fromisoformat(args.current_end))
    else:
        span = max(1, ((hi - lo).days + 1) // 2)
        cur = (hi - timedelta(days=span - 1), hi)
    if args.baseline_start and args.baseline_end:
        base = (date.fromisoformat(args.baseline_start), date.fromisoformat(args.baseline_end))
    else:
        length = (cur[1] - cur[0]).days
        base = (cur[0] - timedelta(days=length + 1), cur[0] - timedelta(days=1))
    if cur[1] < cur[0] or base[1] < base[0]:
        raise SystemExit("explain-spend-change: error: a window's end precedes its start")

    result = {"current_window": [d.isoformat() for d in cur],
              "baseline_window": [d.isoformat() for d in base]}
    if args.dimension:
        result.update(decompose(rows, cur, base, args.dimension))
    else:
        conc = concentration(rows, cur, base)
        result.update(decompose(rows, cur, base, conc["most_concentrated"]))
        result["concentration"] = conc
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
