#!/usr/bin/env python3
"""Classify waste from FOCUS signals; billed and recoverable are different numbers.

The billed dollars of a wasteful resource happened (badge: billing); the
recoverable share is an estimate (badge: estimated), connected by a stated,
overridable recovery rate, never an implied 100%. A resource lands in exactly
one class: double-counting waste inflates the headline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

DEFAULT_CONFIG = {
    "recovery_rates": {"idle": "0.7", "unused_commitment": "1.0",
                       "old_generation": "0.2", "orphaned": "0.8"},
    "old_generation_patterns": [r"m4\.", r"Standard_D\d+_v2", r"n1-standard"],
}
CLASS_ORDER = ["idle", "unused_commitment", "old_generation", "orphaned"]


def classify_row(row: dict, oldgen: list[re.Pattern]) -> str | None:
    category = (row.get("ChargeCategory") or "").strip()
    if category == "Purchase":
        if ((row.get("CommitmentDiscountId") or "").strip()
                and (row.get("CommitmentDiscountStatus") or "").strip() == "Unused"):
            return "unused_commitment"
        return None
    if category != "Usage":
        return None
    cost = Decimal(row.get("BilledCost") or "0")
    if cost <= 0:
        return None
    consumed = (row.get("ConsumedQuantity") or "").strip()
    if consumed and Decimal(consumed) == 0:
        return "idle"  # first match wins: an idle old instance's problem is being on
    haystack = f"{row.get('SkuId') or ''} {row.get('ChargeDescription') or ''}"
    if any(p.search(haystack) for p in oldgen):
        return "old_generation"
    if (row.get("ServiceCategory") or "") == "Storage":
        try:
            tags = json.loads(row.get("Tags") or "{}")
        except json.JSONDecodeError:
            tags = {}
        if "app" not in tags:
            return "orphaned"
    return None


def classify(rows: list[dict], config: dict) -> dict:
    rates = {k: Decimal(v) for k, v in config["recovery_rates"].items()}
    oldgen = [re.compile(p) for p in config["old_generation_patterns"]]

    billed: dict[str, Decimal] = defaultdict(Decimal)
    resources: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for r in rows:
        cls = classify_row(r, oldgen)
        if cls is None:
            continue
        cost = Decimal(r.get("BilledCost") or "0")
        billed[cls] += cost
        name = (r.get("ResourceName") or r.get("CommitmentDiscountId") or "(unnamed)")
        resources[cls][name] += cost

    classes = {}
    total_recoverable = Decimal("0")
    for cls in CLASS_ORDER:
        if cls not in billed:
            continue
        rate = rates[cls]
        recoverable = billed[cls] * rate
        total_recoverable += recoverable
        classes[cls] = {
            "billed_dollars": format(billed[cls], "f"),
            "billed_badge": "billing",
            "recovery_rate_assumed": format(rate, "f"),
            "recoverable_dollars": format(recoverable, ".2f"),
            "recoverable_badge": "estimated",
            "resources": sorted(
                ({"name": n, "dollars": format(v, "f")} for n, v in resources[cls].items()),
                key=lambda x: Decimal(x["dollars"]), reverse=True),
        }
    return {
        "classes": classes,
        "total_recoverable_dollars": format(total_recoverable, ".2f"),
        "total_recoverable_badge": "estimated (sum of estimates; rates are stated assumptions)",
        "rule": "one class per resource, first match in " + " > ".join(CLASS_ORDER),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--config", type=Path)
    args = ap.parse_args()
    config = dict(DEFAULT_CONFIG)
    if args.config:
        config.update(json.loads(args.config.read_text(encoding="utf-8")))
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(classify(rows, config), indent=2))


if __name__ == "__main__":
    main()
