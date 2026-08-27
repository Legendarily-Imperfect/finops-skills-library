#!/usr/bin/env python3
"""Cost per business unit-of-output, with the denominator's provenance printed.

A unit cost nobody can trace to a count source wins an argument once and loses
trust forever, so the units file's source string is echoed verbatim into the
output. Cost-without-units and units-without-cost are findings, not rows to
drop: dropping either fabricates the average.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

COUNT_RE = re.compile(r"^\d+(\.\d+)?$")


class UnitsError(SystemExit):
    def __init__(self, message: str):
        print(f"unit-economics: error: {message}", file=sys.stderr)
        super().__init__(2)


def load_units(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("unit_name"):
        raise UnitsError("units file must name its unit (unit_name)")
    if not data.get("source"):
        raise UnitsError("units file must state its source; an unsourced "
                         "denominator is an unchallengeable number")
    counts = data.get("counts") or data.get("daily")
    if not counts:
        raise UnitsError("units file needs 'counts' (by owner) or 'daily' (by day)")
    for key, v in counts.items():
        if not isinstance(v, str) or not COUNT_RE.match(v):
            raise UnitsError(f"count for {key!r} must be a quoted numeric string, got {v!r}")
    return data


def owner_of(row: dict) -> str:
    if (c := (row.get("x_owner_canonical") or "").strip()):
        return c
    try:
        return json.loads(row.get("Tags") or "{}").get("owner") or "(untagged)"
    except json.JSONDecodeError:
        return "(untagged)"


def unit_costs(rows: list[dict], units: dict) -> dict:
    by_day = "daily" in units
    counts: dict[str, Decimal] = {k: Decimal(v) for k, v in
                                  (units.get("daily") or units["counts"]).items()}
    cost: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        if (r.get("ChargeCategory") or "").strip() != "Usage":
            continue
        key = (r.get("ChargePeriodStart") or "")[:10] if by_day else owner_of(r)
        cost[key] += Decimal(r.get("BilledCost") or "0")

    matched = sorted(set(cost) & set(counts))
    entries = [{
        "key": k,
        "cost": format(cost[k], "f"),
        "units": format(counts[k], "f"),
        "cost_per_unit": format(cost[k] / counts[k], ".6f") if counts[k] else None,
    } for k in matched]
    entries.sort(key=lambda e: Decimal(e["cost_per_unit"] or "0"), reverse=True)

    total_cost = sum((cost[k] for k in matched), Decimal("0"))
    total_units = sum((counts[k] for k in matched), Decimal("0"))
    return {
        "badge": "estimated",
        "unit_name": units["unit_name"],
        "units_source": units["source"],
        "grain": "day" if by_day else "owner",
        "overall_cost_per_unit": format(total_cost / total_units, ".6f") if total_units else None,
        "total_cost": format(total_cost, "f"),
        "total_units": format(total_units, "f"),
        "per_key": entries,
        "cost_without_units": sorted(set(cost) - set(counts)),
        "units_without_cost": sorted(set(counts) - set(cost)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--units", required=True, type=Path)
    args = ap.parse_args()
    units = load_units(args.units)
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(unit_costs(rows, units), indent=2))


if __name__ == "__main__":
    main()
