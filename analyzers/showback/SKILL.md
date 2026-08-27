---
name: showback
description: >-
  Allocate spend by owner and name the untagged remainder, producing the per-owner totals
  a chargeback or showback report is built from. Use when someone asks "who spent what",
  "spend by team", "allocate the bill", "showback report", "chargeback numbers", or "how
  much is unallocated". Run tag-reconcile first: this tool reads the x_owner_canonical
  column it writes (falling back to the raw owner tag when absent), and allocation on
  unreconciled tags silently splits one owner across their spelling variants, which is
  the exact failure showback exists to prevent. The untagged remainder is always its own
  named line, never spread across owners: spreading it hides the governance gap that
  caused it.
---

# showback

## Data Contract

**In:** a FOCUS CSV, ideally through `tag-reconcile` first (uses `x_owner_canonical` when present, else `Tags.owner` verbatim). **Out:** JSON: owners ranked by spend, each with dollars and share; the `(untagged)` line; coverage percent; and the charge categories excluded from allocation (non-Usage rows are reported separately, not allocated, because a commitment purchase belongs to nobody's showback).

## Rules

- **Untagged is a line, not a spread.** Allocating the remainder proportionally makes every owner's number slightly wrong and makes the tagging gap invisible: the two worst outcomes at once.
- **Only Usage allocates.** Purchases, taxes, credits, and adjustments report as their own block; folding them in makes an owner's number move with events they do not control.
- **Shares always sum to 100.0 within rounding**, and the report carries the grand total it allocated so a tie-out can bracket it.

## Usage

```powershell
python reconcile.py --in focus.csv --map owner-map.json --out reconciled.csv   # upstream
python showback.py --in reconciled.csv
python showback.py --in reconciled.csv --report showback.json
python -m pytest -q
```

## Non-Goals

Rate negotiation, amortization policy, and fixing tags (that is `tag-reconcile`). This is the allocation arithmetic, done once, the same way, every month.
