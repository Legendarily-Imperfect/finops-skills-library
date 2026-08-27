#!/usr/bin/env python3
"""Actual vs budget by owner, ranked by variance dollars, with fatal file validation.

Budget amounts are quoted strings, validated as such: an unquoted 2722.00 can
lose its cents before any code sees it. Validation is fatal because a budget
file that is quietly wrong produces a plausible number nobody can reconcile.
Ranked by dollars, not percent: a percent ranking buries the $40K overrun
under a 300% overrun on a $12 budget.
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

AMOUNT_RE = re.compile(r"^\d+(\.\d{1,6})?$")  # no symbols, separators, negatives


class BudgetError(SystemExit):
    def __init__(self, message: str):
        print(f"budget-variance: error: {message}", file=sys.stderr)
        super().__init__(2)


def load_budgets(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    # Duplicate keys: json.loads keeps the last silently; detect on the raw text.
    data = json.loads(raw, object_pairs_hook=_reject_duplicates)
    budgets = data.get("budgets")
    if not budgets:
        raise BudgetError("empty or missing 'budgets' object; a variance report "
                          "against nothing is a plausible-looking lie")
    for owner, amount in budgets.items():
        if not isinstance(amount, str):
            raise BudgetError(f"budget for {owner!r} is not a quoted string "
                              f"({amount!r}); unquoted amounts can lose cents in parsing")
        if not AMOUNT_RE.match(amount):
            raise BudgetError(f"malformed amount for {owner!r}: {amount!r} "
                              "(no symbols, separators, or negatives)")
    return data


def _reject_duplicates(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise BudgetError(f"duplicate key {k!r}; the second value would "
                              "silently overwrite the first")
        seen[k] = v
    return seen


def owner_of(row: dict) -> str:
    if (canon := (row.get("x_owner_canonical") or "").strip()):
        return canon
    try:
        tags = json.loads(row.get("Tags") or "{}")
    except json.JSONDecodeError:
        tags = {}
    return (tags.get("owner") or "").strip() or "(untagged)"


def variance(rows: list[dict], budgets: dict[str, str]) -> dict:
    actuals: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        if (r.get("ChargeCategory") or "").strip() == "Usage":
            actuals[owner_of(r)] += Decimal(r.get("BilledCost") or "0")

    entries = []
    for owner in sorted(set(actuals) | set(budgets)):
        actual = actuals.get(owner, Decimal("0"))
        budget = Decimal(budgets[owner]) if owner in budgets else None
        if budget is None:
            status, var = "no_budget", None
        elif actual == 0:
            status, var = "no_spend", actual - budget
        else:
            var = actual - budget
            status = "over" if var > 0 else "under"
        entries.append({
            "owner": owner, "status": status,
            "actual": format(actual, "f"),
            "budget": format(budget, "f") if budget is not None else None,
            "variance": format(var, "f") if var is not None else None,
            "variance_pct": (format(var / budget * 100, ".1f")
                             if budget not in (None, Decimal("0")) and var is not None else None),
        })
    entries.sort(key=lambda e: Decimal(e["variance"]) if e["variance"] is not None
                 else Decimal("-Infinity"), reverse=True)
    total_actual = sum(actuals.values(), Decimal("0"))
    total_budget = sum((Decimal(v) for v in budgets.values()), Decimal("0"))
    return {
        "totals": {"actual": format(total_actual, "f"),
                   "budget": format(total_budget, "f"),
                   "variance": format(total_actual - total_budget, "f")},
        "by_owner": entries,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--budgets", required=True, type=Path)
    args = ap.parse_args()
    data = load_budgets(args.budgets)
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(json.dumps(variance(rows, data["budgets"]), indent=2))


if __name__ == "__main__":
    main()
