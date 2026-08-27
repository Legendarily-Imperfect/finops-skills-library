---
name: focus-conform
description: >-
  Validate that a dataset actually meets the FOCUS core column contract and name exactly
  what is missing or malformed. Use after focus-normalize, before any analyzer, or whenever
  someone asks "is this FOCUS", "is this file valid", "why does the analyzer choke on this",
  "check this export", or hands you a CSV claiming to be normalized. Checks: required columns
  present, money parseable as Decimal with no scientific notation, dates ISO 8601, currency
  codes sane, ChargeCategory in the allowed set, Tags a valid JSON object, and per-column
  empty-rate warnings. A file that fails here will produce wrong numbers downstream that look
  right, which is why the analyzers refuse un-conformed input by convention.
---

# focus-conform

## Data Contract

**In:** any CSV. **Out:** a report to stdout listing every violation with row numbers (first N occurrences per rule), and an exit code: 0 conforms, 1 conforms with warnings, 2 violations.

## Checks

| Rule | Severity | Why It Is Fatal |
|---|---|---|
| Required FOCUS columns present | violation | Analyzers index by name; a missing column is a silent zero downstream |
| Money parses as Decimal, no scientific notation, no currency symbols or thousands separators | violation | `float()` round trips and `$1,234` both corrupt sums invisibly |
| `ChargePeriodStart`/`End` are ISO 8601 dates or datetimes | violation | Window math on mixed formats drops rows without erroring |
| `ChargeCategory` in the FOCUS set (Usage, Purchase, Tax, Credit, Adjustment) | violation | Unknown categories silently escape both cost and credit totals |
| `Tags` is a JSON object (not array, not bare string) | violation | Tag tools iterate keys; an array row poisons the fold |
| `BillingCurrency` present when any money present | violation | Mixed-currency sums are the worst silent error in the domain |
| Empty-rate per column above 50% | warning | Usually a mapping gap, sometimes legitimate (commitment rows have no ResourceId) |

## Usage

```powershell
python conform.py --in focus.csv               # human report, exit code says it all
python conform.py --in focus.csv --max-examples 10
python -m pytest -q
```

## Non-Goals

Fixing anything. This tool only names problems; `focus-normalize` is where fixes belong (usually a mapping edit). It also does not validate the full FOCUS spec, only the core column contract this library standardizes on.
