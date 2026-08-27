#!/usr/bin/env python3
"""Three-leg spend reconciliation that names gap causes instead of printing a difference.

Legs: A the source of record (invoice or export total), B the working FOCUS
dataset, C optionally the downstream app or report. A tie-out that stops at
"off by $3,412" has done nothing; the value is the quantified checklist of
known causes, computed from the dataset itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def profile(rows: list[dict]) -> dict:
    """Everything about the dataset a gap investigation reaches for first."""
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    by_provider: dict[str, Decimal] = defaultdict(Decimal)
    currencies: set[str] = set()
    credits = Decimal("0")
    total = Decimal("0")
    dates: list[str] = []
    for r in rows:
        cost = Decimal(r.get("BilledCost") or "0")
        total += cost
        by_category[r.get("ChargeCategory") or "(none)"] += cost
        by_provider[r.get("ProviderName") or "(none)"] += cost
        if (c := (r.get("BillingCurrency") or "").strip()):
            currencies.add(c)
        if cost < 0:
            credits += cost
        if (d := (r.get("ChargePeriodStart") or "").strip()):
            dates.append(d)
    return {
        "total": total,
        "by_category": {k: format(v, "f") for k, v in sorted(by_category.items())},
        "by_provider": {k: format(v, "f") for k, v in sorted(by_provider.items())},
        "currencies": sorted(currencies),
        "credit_dollars": format(credits, "f"),
        "window_covered": {"min": min(dates), "max": max(dates)} if dates else None,
        "row_count": len(rows),
    }


def compare(name_a: str, total_a: Decimal, name_b: str, total_b: Decimal,
            tolerance: Decimal, prof: dict) -> dict:
    diff = total_b - total_a
    verdict = "tie" if abs(diff) <= tolerance else "gap"
    result = {
        "legs": f"{name_a} vs {name_b}",
        "verdict": verdict,
        f"{name_a}_total": format(total_a, "f"),
        f"{name_b}_total": format(total_b, "f"),
        "difference": format(diff, "f"),
        "tolerance": format(tolerance, "f"),
    }
    if verdict == "gap":
        causes = []
        # 1. A whole non-Usage category close to the gap is the usual suspect.
        for cat, dollars in prof["by_category"].items():
            if cat != "Usage" and Decimal(dollars) != 0:
                causes.append({"cause": f"category {cat!r} counted on one side only",
                               "dollars": dollars,
                               "explains_gap": abs(Decimal(dollars) - abs(diff)) <= tolerance})
        # 2. Credits netted on one side.
        if Decimal(prof["credit_dollars"]) != 0:
            causes.append({"cause": "credits netted on one side only",
                           "dollars": prof["credit_dollars"],
                           "explains_gap": abs(Decimal(prof["credit_dollars"]) + abs(diff)) <= tolerance
                                            or abs(-Decimal(prof["credit_dollars"]) - abs(diff)) <= tolerance})
        # 3. Window drift is visible from the profile; flag, cannot quantify blind.
        causes.append({"cause": "calendar vs invoice period",
                       "check": f"rows cover {prof['window_covered']}; compare to the source's period"})
        # 4. Scope: a whole provider missing from one side.
        for prov, dollars in prof["by_provider"].items():
            if abs(Decimal(dollars) - abs(diff)) <= tolerance:
                causes.append({"cause": f"provider {prov!r} filtered from one side",
                               "dollars": dollars, "explains_gap": True})
        result["candidate_causes"] = causes
    if len(prof["currencies"]) > 1:
        result["red_flag"] = f"mixed currencies in dataset: {prof['currencies']}; no math is trustworthy until resolved"
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--focus", required=True, type=Path)
    ap.add_argument("--source-total", required=True)
    ap.add_argument("--source-name", default="source")
    ap.add_argument("--app-total")
    ap.add_argument("--app-name", default="app")
    ap.add_argument("--tolerance", default="0.01")
    args = ap.parse_args()

    with args.focus.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    prof = profile(rows)
    tol = Decimal(args.tolerance)

    results = [compare(args.source_name, Decimal(args.source_total), "dataset", prof["total"], tol, prof)]
    if args.app_total is not None:
        results.append(compare("dataset", prof["total"], args.app_name, Decimal(args.app_total), tol, prof))

    print(json.dumps({"profile": {k: v for k, v in prof.items() if k != "total"},
                      "dataset_total": format(prof["total"], "f"),
                      "comparisons": results}, indent=2))
    sys.exit(0 if all(r["verdict"] == "tie" for r in results) else 1)


if __name__ == "__main__":
    main()
