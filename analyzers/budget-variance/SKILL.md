---
name: budget-variance
description: >-
  Actual against budget by owner, ranked by dollar overspend, with the file-format
  discipline that keeps cents from vanishing. Use when someone asks "who is over budget",
  "variance report", "actual vs plan", "how are we tracking against budget", or hands you
  a budget file. Budgets arrive as a JSON file with amounts as QUOTED STRINGS: an unquoted
  2722.00 loses its cents in some parsers before any code sees it, so quoting is validated,
  not suggested. Validation is fatal, not warning: a duplicate owner silently overwrites in
  every map type, a malformed amount surfaces at 2am inside a mail library, and a budget
  file that is quietly wrong produces a plausible number nobody can reconcile later.
  Ranked by variance dollars, because a percent-ranked list buries the $40K overrun under
  a 300% overrun on a $12 budget.
---

# budget-variance

## Data Contract

**In:** a FOCUS CSV (through `tag-reconcile`, same owner rule as `showback`) and `budgets.json`:

```json
{
  "period": "2026-06",
  "budgets": {"Atlas": "5000.00", "Cascade": "3200.00"},
  "alertees": {"Atlas": ["owner-atlas@example.com"]}
}
```

**Out:** JSON: per-owner actual, budget, variance dollars and percent, status (`over` / `under` / `no_budget` / `no_spend`), ranked by variance dollars descending; totals across all owners.

## Fatal Validations

| Condition | Why fatal, not warning |
|---|---|
| Unquoted amount (JSON number) | Cents can be gone before any code sees the value; the file format is the contract |
| Duplicate owner key | The second silently overwrites the first in every parser |
| Malformed amount (symbols, separators, negatives) | Surfaces later in the worst place; fail at read time |
| Empty budgets object | A variance report against nothing is a plausible-looking lie |

Owners with spend but no budget, and budgets with no spend, are reported as their own statuses: both are findings, not errors.

## Usage

```powershell
python variance.py --in reconciled.csv --budgets budgets.json
python -m pytest -q
```

## Non-Goals

Forecast (that is `forecast`), alert delivery (wire alertees into your notifier), and budget setting. This is the comparison, ranked so the report's first line is the biggest problem.
