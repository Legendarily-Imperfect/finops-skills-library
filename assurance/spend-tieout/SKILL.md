---
name: spend-tieout
description: >-
  Reconcile your analyzed spend against the source of record and name the cause of any gap
  instead of printing a difference. Use before any number leaves the building: "does this
  report tie out", "why doesn't our dashboard match the invoice", "reconcile the totals",
  "can we trust this number", "the CFO says the bill was different". Three legs: the source
  of record (invoice or billing-export total), the working dataset (FOCUS CSV), and
  optionally the downstream app or report total. A tie-out that prints "off by $3,412" has
  done nothing; this one walks a checklist of the known gap causes (excluded categories such
  as Marketplace or Tax, credits netted on one side only, calendar versus invoice period,
  scope filters, currency) and quantifies which of them explains the gap. Run sync-check
  first: reconciling against a stale downstream proves nothing.
---

# spend-tieout

## Data Contract

**In:** `--focus data.csv` (leg B), `--source-total N` with `--source-name` (leg A), optional `--app-total N` (leg C), optional `--tolerance` (absolute dollars, default 0.01).

**Out:** a JSON verdict per leg pair: `tie` or `gap`, the signed difference, and for gaps a quantified breakdown of candidate causes drawn from the dataset itself (dollars by ChargeCategory, credits present, window actually covered by the rows versus the window claimed). Exit 0 when every compared pair ties, 1 otherwise.

## The Known Gap Causes, Checked In Order

1. **Excluded categories.** Tax, Credit, Purchase, or Marketplace-like rows counted on one side only. The report shows dollars per ChargeCategory so the excluded slice is visible immediately.
2. **Credits netted on one side.** Negative rows present in the data but netted out of the source figure, or vice versa.
3. **Calendar versus invoice period.** The rows' actual min/max ChargePeriodStart is printed beside the claimed window; a row from the wrong month is the single most common cause.
4. **Scope filters.** A subaccount or provider filtered from one side. Dollars by ProviderName make a missing cloud obvious.
5. **Currency.** Mixed BillingCurrency values in the data are reported as an immediate red flag before any other math is trusted.

## Usage

```powershell
python tieout.py --focus focus.csv --source-total 156656.36 --source-name "GCP invoice June"
python tieout.py --focus focus.csv --source-total 156656.36 --app-total 156650.00 --tolerance 10
python -m pytest -q
```

## Non-Goals

Fetching either outside total (the invoice is yours to read; the app is behind your auth), and fixing anything. This tool renders a verdict and arms the investigation.
