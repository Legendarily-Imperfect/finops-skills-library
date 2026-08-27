#!/usr/bin/env python3
"""Validate a CSV against the FOCUS core column contract; name every violation.

Exit codes: 0 conforms, 1 warnings only, 2 violations. This tool fixes nothing:
a fix belongs in focus-normalize (usually a mapping edit), and a validator that
also mutates is a validator whose report you can no longer trust.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = [
    "BillingAccountId", "ChargePeriodStart", "ChargePeriodEnd",
    "BilledCost", "BillingCurrency", "ChargeCategory",
    "ProviderName", "ServiceName", "Tags",
]
MONEY_COLUMNS = ["BilledCost", "EffectiveCost", "ListCost", "ContractedCost"]
CHARGE_CATEGORIES = {"Usage", "Purchase", "Tax", "Credit", "Adjustment"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
# Plain decimal only: no exponent, no symbols, no separators.
PLAIN_MONEY = re.compile(r"^-?\d+(\.\d+)?$")
EMPTY_WARN_RATE = 0.50


def check(path: Path, max_examples: int) -> tuple[list[str], list[str]]:
    violations: dict[str, list[str]] = defaultdict(list)
    warnings: list[str] = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            return [f"missing required columns: {missing}"], []

        empty_counts: dict[str, int] = defaultdict(int)
        total = 0
        for i, row in enumerate(reader, start=2):
            total += 1
            for col in header:
                if not (row.get(col) or "").strip():
                    empty_counts[col] += 1

            for col in MONEY_COLUMNS:
                v = (row.get(col) or "").strip()
                if v == "":
                    continue
                if not PLAIN_MONEY.match(v):
                    violations[f"money format {col}"].append(f"row {i}: {v!r}")
                else:
                    try:
                        Decimal(v)
                    except InvalidOperation:
                        violations[f"money parse {col}"].append(f"row {i}: {v!r}")

            for col in ("ChargePeriodStart", "ChargePeriodEnd"):
                v = (row.get(col) or "").strip()
                if v and not ISO_DATE.match(v):
                    violations[f"date format {col}"].append(f"row {i}: {v!r}")

            cat = (row.get("ChargeCategory") or "").strip()
            if cat and cat not in CHARGE_CATEGORIES:
                violations["ChargeCategory outside FOCUS set"].append(f"row {i}: {cat!r}")

            tags = (row.get("Tags") or "").strip()
            if tags:
                try:
                    parsed = json.loads(tags)
                    if not isinstance(parsed, dict):
                        violations["Tags not a JSON object"].append(f"row {i}: {type(parsed).__name__}")
                except json.JSONDecodeError:
                    violations["Tags invalid JSON"].append(f"row {i}: {tags[:40]!r}")

            has_money = any((row.get(c) or "").strip() for c in MONEY_COLUMNS)
            if has_money and not (row.get("BillingCurrency") or "").strip():
                violations["money without BillingCurrency"].append(f"row {i}")

        if total:
            for col, n in sorted(empty_counts.items()):
                rate = n / total
                if rate > EMPTY_WARN_RATE and col in REQUIRED_COLUMNS:
                    warnings.append(f"column {col!r} is {rate:.0%} empty ({n}/{total} rows); "
                                    "usually a mapping gap")

    flat = []
    for rule, examples in violations.items():
        shown = examples[:max_examples]
        more = f" (+{len(examples) - len(shown)} more)" if len(examples) > len(shown) else ""
        flat.append(f"{rule}: {len(examples)} occurrence(s): {'; '.join(shown)}{more}")
    return flat, warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--max-examples", type=int, default=5)
    args = ap.parse_args()

    violations, warnings = check(args.src, args.max_examples)
    for v in violations:
        print(f"VIOLATION  {v}")
    for w in warnings:
        print(f"WARNING    {w}")
    if violations:
        print(f"focus-conform: {args.src.name} FAILS the core contract "
              f"({len(violations)} rule(s) violated)")
        sys.exit(2)
    if warnings:
        print(f"focus-conform: {args.src.name} conforms with {len(warnings)} warning(s)")
        sys.exit(1)
    print(f"focus-conform: {args.src.name} conforms")
    sys.exit(0)


if __name__ == "__main__":
    main()
