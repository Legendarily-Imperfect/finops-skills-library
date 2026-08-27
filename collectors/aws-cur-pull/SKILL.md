---
name: aws-cur-pull
description: >-
  Pull an AWS Cost and Usage Report (Data Exports, CUR 2.0) from its S3 delivery bucket
  into one local CSV that focus-normalize's aws_cur2 mapping consumes directly. Use when
  someone says "get our AWS spend", "download the CUR", "pull the cost and usage report",
  "AWS billing data", or is about to hand-download billing-period folders. CUR delivery
  is a folder of gzipped CSV parts per billing period, and the mistakes this skill
  prevents are concatenation mistakes: every part's header must match before parts are
  joined (a schema change mid-period otherwise shifts columns silently), and a period is
  pulled whole, never appended to, because AWS restates files within a period. Live mode
  uses the aws CLI; --emit-cli prints the exact commands for zero-access use.
---

# aws-cur-pull

## Data Contract

**In:** bucket, prefix, export name, billing period (`--period 2026-06`). **Out:** one CSV (`--out`), parts concatenated with exactly one header, ready for `focus-normalize --mapping aws_cur2`. The export must be configured as CSV (gzip); Parquet exports are out of scope in v1 and detected by extension with a clear error.

## Rules

- **Headers must match across parts before any join.** A mid-period schema change otherwise shifts columns silently, and the corrupted file still parses.
- **Pull the period whole; never append.** AWS restates files within a billing period; the folder is the truth, yesterday's download is not.
- **CSV (gzip) only in v1.** A `.parquet` part is a named error pointing at the export configuration, not a silent skip.

## Usage

```powershell
# Zero-access: print the exact aws CLI commands and expected layout
python aws_pull.py --bucket my-cur-bucket --prefix cur/ --export-name daily-cur --period 2026-06 --emit-cli

# Live: sync the period's parts and concatenate
python aws_pull.py --bucket my-cur-bucket --prefix cur/ --export-name daily-cur --period 2026-06 --out aws.csv
```

## Prerequisites Beyond The Baseline

Live mode needs the `aws` CLI authenticated with `s3:GetObject`/`s3:ListBucket` on the delivery bucket. `--emit-cli` needs nothing.

## Non-Goals

Creating the export (one-time console/API setup), Parquet, Athena, and normalization (downstream).
