#!/usr/bin/env python3
"""Commitment coverage and utilization, reported together, unused commitments named.

Coverage without utilization hides dead commitments inside a green number.
Eligibility is a stated category list: counting uncoverable spend in the
denominator understates coverage dishonestly.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

DEFAULT_ELIGIBLE = ["Compute", "Databases"]


def analyze(rows: list[dict], eligible_categories: list[str]) -> dict:
    eligible = set(eligible_categories)
    eligible_usage = covered_usage = Decimal("0")
    purchased = unused_dollars = Decimal("0")
    unused: list[dict] = []
    by_provider: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"eligible": Decimal("0"), "covered": Decimal("0")})

    for r in rows:
        cost = Decimal(r.get("BilledCost") or "0")
        category = (r.get("ChargeCategory") or "").strip()
        commit_id = (r.get("CommitmentDiscountId") or "").strip()
        provider = r.get("ProviderName") or "(none)"
        if category == "Usage" and (r.get("ServiceCategory") or "") in eligible:
            eligible_usage += cost
            by_provider[provider]["eligible"] += cost
            if commit_id:
                covered_usage += cost
                by_provider[provider]["covered"] += cost
        elif category == "Purchase" and commit_id:
            purchased += cost
            if (r.get("CommitmentDiscountStatus") or "").strip() == "Unused":
                unused_dollars += cost
                unused.append({"id": commit_id, "provider": provider,
                               "dollars": format(cost, "f")})

    used = purchased - unused_dollars
    return {
        "badge": "billing",
        "eligible_categories": sorted(eligible),
        "eligible_usage_dollars": format(eligible_usage, "f"),
        "covered_usage_dollars": format(covered_usage, "f"),
        "coverage_pct": format(covered_usage / eligible_usage * 100, ".1f")
                        if eligible_usage else "0.0",
        "commitment_purchase_dollars": format(purchased, "f"),
        "utilization_pct": format(used / purchased * 100, ".1f") if purchased else None,
        "unused_commitment_dollars": format(unused_dollars, "f"),
        "unused_commitments": sorted(unused, key=lambda u: Decimal(u["dollars"]), reverse=True),
        "by_provider": {
            p: {"coverage_pct": format(v["covered"] / v["eligible"] * 100, ".1f")
                               if v["eligible"] else "0.0",
                "eligible_dollars": format(v["eligible"], "f")}
            for p, v in sorted(by_provider.items())},
        "note": "coverage and utilization travel together; one without the other "
                "is how programs lose money behind a green dashboard",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--eligible-categories", nargs="+", default=DEFAULT_ELIGIBLE)
    args = ap.parse_args()
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(analyze(rows, args.eligible_categories), indent=2))


if __name__ == "__main__":
    main()
