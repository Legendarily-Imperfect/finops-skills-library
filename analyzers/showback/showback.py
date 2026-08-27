#!/usr/bin/env python3
"""Per-owner spend allocation with the untagged remainder as its own named line.

Untagged is a line, not a spread: allocating the remainder proportionally makes
every owner's number slightly wrong and hides the governance gap that caused
it. Only Usage rows allocate; other categories report separately because a
commitment purchase belongs to nobody's showback.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

UNTAGGED = "(untagged)"


def owner_of(row: dict) -> str:
    if (canon := (row.get("x_owner_canonical") or "").strip()):
        return canon
    try:
        tags = json.loads(row.get("Tags") or "{}")
    except json.JSONDecodeError:
        tags = {}
    return (tags.get("owner") or "").strip() or UNTAGGED


def showback(rows: list[dict]) -> dict:
    by_owner: dict[str, Decimal] = defaultdict(Decimal)
    excluded: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        cost = Decimal(r.get("BilledCost") or "0")
        category = (r.get("ChargeCategory") or "").strip() or "(none)"
        if category == "Usage":
            by_owner[owner_of(r)] += cost
        else:
            excluded[category] += cost

    allocated = sum(by_owner.values(), Decimal("0"))
    untagged = by_owner.get(UNTAGGED, Decimal("0"))
    owners = sorted(
        ({"owner": k, "dollars": format(v, "f"),
          "share_pct": format(v / allocated * 100, ".1f") if allocated else "0.0"}
         for k, v in by_owner.items()),
        key=lambda o: Decimal(o["dollars"]), reverse=True)
    return {
        "allocated_total": format(allocated, "f"),
        "coverage_pct": format((allocated - untagged) / allocated * 100, ".1f") if allocated else "100.0",
        "owners": owners,
        "excluded_categories": {k: format(v, "f") for k, v in sorted(excluded.items())},
        "note": "untagged is a named line, never spread; non-Usage categories are not allocated",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    payload = json.dumps(showback(rows), indent=2)
    if args.report:
        args.report.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
