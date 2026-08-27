---
name: unit-economics
description: >-
  Cost per unit the business actually runs on: per customer, per transaction, per order,
  per tenant, per active user. Use when someone asks "what does a customer cost us", "is
  our cost per transaction going up", "unit costs", "cost per tenant", or when leadership
  wants spend tied to business output instead of raw totals. Spend rising 20% while
  transactions rise 40% is a cost story going WELL, and only a unit number shows it.
  Units arrive from the business (a CSV or JSON you supply); this tool never invents
  them, and the honesty rule is the denominator's: cost per unit is only as real as the
  unit count, so the source and period of the counts are echoed into the output where a
  reader can challenge them.
---

# unit-economics

## Data Contract

**In:** a FOCUS CSV (owner rule as elsewhere: `x_owner_canonical` else `Tags.owner`) and a units file:

```json
{"unit_name": "transactions", "source": "billing DB export 2026-06", "counts": {"Atlas": "120000", "Cascade": "85000"}}
```

or per-day: `{"unit_name": "orders", "source": "...", "daily": {"2026-06-01": "4100"}}`. Counts are quoted strings, same discipline as budgets.

**Out:** JSON: cost per unit by owner (or by day), total cost, total units, the unit name and **source echoed verbatim**, owners with cost but no units and units but no cost listed separately, everything badged `estimated` because allocation upstream is.

## Rules

- **The denominator's provenance prints.** A unit cost nobody can trace to a count source is a number that wins an argument once and loses trust forever.
- **Mismatches are findings.** Cost with no units (untracked product?) and units with no cost (mis-tagged spend?) each get their own list; silently dropping either fabricates the average.
- **Only Usage spend enters**, same reason as showback.

## Usage

```powershell
python unitcost.py --in reconciled.csv --units units.json
python -m pytest -q
```

## Non-Goals

Counting units (the business system of record owns that), margin math (revenue is not in scope), and cross-period trending in v1 (run per period and diff).
