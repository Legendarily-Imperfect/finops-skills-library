---
name: waste-classify
description: >-
  Sort spend into named waste classes with every figure badged billing or estimated and a
  stated recovery rate. Use when someone asks "how much are we wasting", "where's the
  waste", "what can we cut", "cost optimization opportunities", or before any savings
  claim leaves the building. Classes in v1, detected from FOCUS signals alone: idle
  (billed with ~zero consumed quantity), unused commitments (purchased, status Unused),
  old generation (SKU or description matches a configurable pattern list), orphaned
  (storage carrying no application tag). The honesty rules are the product: the billed
  dollars of a wasteful resource are BILLING (they happened), but the recoverable share is
  ESTIMATED (you rarely recover 100%: migrations cost, some idle is standby), so every
  class reports both numbers and the recovery rate that connects them is a stated,
  overridable assumption, never an implied 100%.
---

# waste-classify

## Data Contract

**In:** a FOCUS CSV, optional `--config waste-config.json` overriding recovery rates and old-generation patterns:

```json
{
  "recovery_rates": {"idle": "0.7", "unused_commitment": "1.0", "old_generation": "0.2", "orphaned": "0.8"},
  "old_generation_patterns": ["m4\\.", "Standard_D\\d+_v2", "n1-standard"]
}
```

**Out:** JSON per class: billed dollars (badge `billing`), estimated recoverable dollars (badge `estimated`), the recovery rate applied, and the resources ranked by dollars. Plus a total recoverable figure that is explicitly the sum of estimates.

## Rules

- **Billed and recoverable are different numbers with different badges.** Presenting billed waste as recoverable savings is the most common dishonesty in optimization decks.
- **Recovery rates are stated assumptions.** Defaults: idle 0.7 (some idle is standby or failover), unused commitment 1.0 (a dead commitment is fully recoverable at renewal), old generation 0.2 (only the price delta recovers, and migration costs eat some), orphaned 0.8. Override per environment; the report prints whichever were used.
- **A resource lands in one class**, the first that matches (idle beats old-generation: an idle old instance's problem is that it is on, not its generation). Double-counting waste inflates the headline.

## Usage

```powershell
python classify.py --in focus.csv
python classify.py --in focus.csv --config waste-config.json
python -m pytest -q
```

## Non-Goals

Rightsizing running-but-oversized workloads (that is `rightsize-on-peaks`, which needs utilization data FOCUS does not carry), and executing any of it: this names the money and its evidence, people decide.
