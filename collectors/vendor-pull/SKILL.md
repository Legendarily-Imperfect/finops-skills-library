---
name: vendor-pull
description: >-
  Pull spend data from a cost platform's API (Ternary, Vantage, Cloudability, or any
  paged REST endpoint) for shops that never touch raw billing. Use when someone says
  "pull from our cost tool", "get the data out of the platform", "export from the API",
  or the billing data lives behind a vendor rather than a cloud export. The trap this
  skill was built on, with the measurement that proved it: OFFSET PAGING IS WRONG, NOT
  SLOW. When the sort key is not unique across the queried dimensions, rows on page
  boundaries duplicate while others drop; measured against an unpaged read of one month:
  $7,775 low at page size 500, $1,922 high at 2,000, from identical data, silently, wrong
  in both directions. The correct partition cuts CARDINALITY, not time: calendar months
  first (each a complete read on a natural boundary), then a sub-dimension within an
  overflowing month, and when a single partition still fills the row cap the tool RAISES
  rather than returning a truncated read that looks complete.
---

# vendor-pull

## Data Contract

**In:** `vendor-config.json` naming the endpoint, auth (an environment variable holding the token, never a value in the file), row cap, and partition sub-dimension; a date range. **Out:** CSV of the vendor's rows plus a pull manifest (partitions fetched, row counts, any refusals), ready for a vendor-specific `focus-normalize` mapping you add.

```json
{
  "base_url": "https://api.example.com/query",
  "auth_env": "VENDOR_API_TOKEN",
  "row_cap": 10000,
  "partition_dimension": "cloud",
  "partition_values": ["aws", "azure", "gcp"]
}
```

## Rules

- **Months, then sub-dimension, never offset.** Bisecting the date range does not help when precision is monthly: row count tracks live dimension combinations, not window width. A single day can return nearly the same row set as its whole month.
- **Raise on overflow, never truncate.** A partition that fills the row cap after both cuts raises with the partition named. A truncated read looks complete, and that is the worst property data can have.
- **Disjoint and exhaustive, so parts sum to the whole.** Both partition axes are chosen for that property; the manifest proves coverage.
- **Tokens come from the environment.** The config file names the variable; it never holds the value.

## Usage

```powershell
python vendor_pull.py --config vendor-config.json --start 2026-04 --end 2026-06 --out vendor.csv
python -m pytest -q
```

## Non-Goals

Vendor-specific field mappings (write a `focus-normalize` mapping for your vendor's columns), streaming, and write access of any kind.
