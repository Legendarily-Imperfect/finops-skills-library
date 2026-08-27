---
name: azure-cost-pull
description: >-
  Pull an Azure Cost Management export from its storage account into one local CSV that
  focus-normalize's azure_cost mapping consumes directly. Use when someone says "get our
  Azure spend", "download the cost export", "Azure billing data", "pull costs from the
  storage account". Azure exports drop dated CSV files under a container path per run,
  and the traps are Azure-specific: the export writes a NEW file per run and old runs
  linger, so only the latest file for the period is real (concatenating a folder
  double-counts every earlier run); amounts arrive in the billing currency column with
  regional decimal separators possible in older schemas; and the amortized and actual
  exports have different columns, so the export type is stated, not guessed. Live mode
  uses the az CLI; --emit-cli prints the exact commands for zero-access use.
---

# azure-cost-pull

## Data Contract

**In:** storage account, container, export path, period (`--period 2026-06`). **Out:** one CSV (`--out`): the **latest run's file** for the period, selected by the run timestamp in the blob path, ready for `focus-normalize --mapping azure_cost`.

## Rules

- **Latest run only, never the folder.** Each export run writes a new file and old runs linger; concatenating a folder double-counts every earlier run. The tool lists, sorts by run, takes the newest, and prints which it chose so the choice is auditable.
- **Export type is stated.** `--type actual` or `--type amortized`; the two have different columns and mixing them in one dataset reconciles to nothing.
- **Decimal-comma detection.** If the cost column parses better with `,` as the decimal separator, the tool says so and refuses rather than guessing: a silent locale guess is a hundredfold error in either direction.

## Usage

```powershell
python azure_pull.py --account mystorageacct --container exports --path daily-costs --period 2026-06 --emit-cli
python azure_pull.py --account mystorageacct --container exports --path daily-costs --period 2026-06 --type actual --out azure.csv
```

## Prerequisites Beyond The Baseline

Live mode needs the `az` CLI logged in with Storage Blob Data Reader on the container. `--emit-cli` needs nothing.

## Non-Goals

Creating the export (one-time portal/API setup), the Query API (a later addition), and normalization (downstream).
