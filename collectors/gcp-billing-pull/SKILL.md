---
name: gcp-billing-pull
description: >-
  Pull the GCP BigQuery billing export correctly and cheaply. Use when someone says "get
  GCP spend", "query the billing export", "pull our GCP costs", "billing data for the last
  N days", or is about to write their own query against gcp_billing_export_v1. The trap
  this skill exists for: the export table is partitioned on ingestion time, so a correct
  query filters BOTH _PARTITIONTIME (prunes partitions, controls scan cost) AND
  usage_start_time (the correct predicate), and a correction to old usage lands in a NEW
  partition, so windows are rebuilt, never appended. Getting either wrong reads complete
  and is silently wrong or expensive. Emits flattened column names that focus-normalize's
  gcp_billing mapping consumes directly.
---

# gcp-billing-pull

## Data Contract

**In:** a project, dataset, and table name for the standard usage cost export, a trailing-day window or explicit dates. **Out:** CSV with flattened columns (`billing_account_id`, `usage_start_time`, `cost`, `currency`, `service_description`, `sku_description`, `sku_id`, `project_id`, `project_name`, `location_region`, `resource_name`, `resource_global_name`, `usage_amount`, `usage_unit`, `labels` as a JSON array string), ready for `focus-normalize --mapping gcp_billing`.

## The Rules, With The Measurements That Earned Them

- **Filter both `_PARTITIONTIME` and `usage_start_time`.** The table is ingestion-time partitioned: `_PARTITIONTIME` prunes partitions, `usage_start_time` is the correct predicate. Measured on a seven-day sum: `usage_start_time` alone scanned 0.13 TB; both together scanned about a hundredth of that. The partition filter gets padding on both sides because corrections to old usage arrive in new partitions.
- **Rebuild a trailing window; never append yesterday.** Billing corrects retroactively: a restated line for last Tuesday arrives in today's partition. The default window is 10 trailing days, the working estimate of how far corrections reach.
- **`usage.amount` is tokens or units even where `usage.unit` reads strangely; `cost` is already net of contract discounts** where the account has them. Do not re-apply a discount ratio.

## Usage

```powershell
# Print the SQL without running it (works with no GCP access at all):
python gcp_pull.py --project my-proj --dataset billing --table gcp_billing_export_v1_XXXX --days 10 --emit-sql

# Run via the bq CLI (requires gcloud auth and the bq tool):
python gcp_pull.py --project my-proj --dataset billing --table gcp_billing_export_v1_XXXX --days 10 --out gcp.csv
```

## Prerequisites Beyond The Baseline

Live mode needs the `bq` CLI (ships with the Google Cloud SDK) and an authenticated account with `bigquery.jobs.create` on the project and read on the export dataset. `--emit-sql` needs nothing: paste the SQL into the console if you prefer.

## Failure Modes

- `bq` missing or unauthenticated: exits 2 telling you so and pointing at `--emit-sql` as the no-access path.
- An end date before the start date: exits 2 rather than producing a negative window.

## Non-Goals

Normalization (that is `focus-normalize`), detailed-export and pricing-export tables (v1 targets the standard usage cost export), and any write to BigQuery: this tool only ever reads.
