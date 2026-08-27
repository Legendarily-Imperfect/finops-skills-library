---
name: commitment-coverage
description: >-
  Report commitment coverage (reserved instances, savings plans, committed use discounts)
  against eligible usage, and name the unused commitments burning money. Use when someone
  asks "what's our RI coverage", "are we wasting savings plans", "should we buy
  commitments", "CUD utilization", "committed vs on-demand". Two numbers with opposite
  failure modes, always reported together: coverage (share of eligible usage under a
  commitment; low means paying on-demand rates for steady load) and utilization (share of
  purchased commitment actually used; low means paying for capacity nobody uses). A high
  coverage number quoted without utilization hides dead commitments inside it, which is
  how a savings program loses money while its dashboard is green.
---

# commitment-coverage

## Data Contract

**In:** a FOCUS CSV. Commitment-covered usage is identified by `CommitmentDiscountId` being non-empty on Usage rows; commitment purchases are `ChargeCategory=Purchase` rows with a `CommitmentDiscountId`; `CommitmentDiscountStatus=Unused` marks purchased-but-idle commitment. Eligible usage defaults to `ServiceCategory` Compute and Databases (`--eligible-categories` to override). **Out:** JSON: coverage percent, utilization percent, eligible usage dollars, covered dollars, committed purchase dollars, unused commitment dollars with each unused commitment named, and per-provider breakdowns.

## Rules

- **Coverage and utilization travel together.** One without the other is how programs lose money behind a green dashboard.
- **Unused commitments are named individually**, with dollars: an aggregate "utilization 92%" hides which commitment is dead and who should act.
- **Eligibility is a stated list, not everything**: storage and egress cannot be covered by compute commitments, and counting them in the denominator flatters nobody's coverage but understates it dishonestly.
- Figures from the bill are badged `billing`; nothing here is estimated.

## Usage

```powershell
python coverage.py --in focus.csv
python coverage.py --in focus.csv --eligible-categories Compute
python -m pytest -q
```

## Non-Goals

Purchase recommendations (what to buy needs price and term data), and amortization policy. This reports the current position honestly; the buying decision is a different tool with different inputs.
