#!/usr/bin/env python3
"""Pull a CUR 2.0 billing period from S3 and concatenate its parts safely.

Two rules do the work: every part's header must match before parts are joined
(a mid-period schema change otherwise shifts columns silently, and the
corrupted file still parses), and a period is pulled whole, never appended,
because AWS restates files within a billing period.
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# CUR 2.0 (Data Exports) column names are snake_case; the aws_cur2 mapping in
# focus-normalize fingerprints on these. The seam test keeps the two in step.
KNOWN_CUR2_COLUMNS = [
    "bill_payer_account_id", "bill_billing_period_start_date",
    "bill_billing_period_end_date", "line_item_usage_account_id",
    "line_item_usage_start_date", "line_item_usage_end_date",
    "line_item_line_item_type", "line_item_product_code",
    "line_item_resource_id", "line_item_usage_amount",
    "line_item_unblended_cost", "line_item_net_unblended_cost",
    "line_item_currency_code", "line_item_line_item_description",
    "pricing_public_on_demand_cost", "pricing_unit",
    "product_region", "product_sku",
]


def period_prefix(prefix: str, export_name: str, period: str) -> str:
    """Data Exports layout: {prefix}/{export}/data/BILLING_PERIOD={YYYY-MM}/"""
    base = prefix.strip("/")
    return f"{base}/{export_name}/data/BILLING_PERIOD={period}/"


def emit_cli(bucket: str, pfx: str, workdir: str) -> str:
    return (
        f"aws s3 sync s3://{bucket}/{pfx} {workdir} --exclude * --include *.csv.gz\n"
        f"# then run this tool again with --local-dir {workdir} to concatenate safely"
    )


def concatenate(parts: list[Path], out: Path) -> int:
    """Join gz parts with exactly one header; refuse on any header mismatch."""
    if not parts:
        raise SystemExit("aws-cur-pull: error: no .csv.gz parts found for the period")
    bad = [p for p in parts if p.suffix == ".parquet"]
    if bad:
        raise SystemExit("aws-cur-pull: error: Parquet parts found; this tool handles "
                         "CSV (gzip) exports only. Reconfigure the Data Export to CSV.")
    header: str | None = None
    rows = 0
    with out.open("w", encoding="utf-8", newline="") as w:
        for p in sorted(parts):
            opener = gzip.open if p.name.endswith(".gz") else open
            with opener(p, "rt", encoding="utf-8", newline="") as f:
                first = f.readline().rstrip("\r\n")
                if header is None:
                    header = first
                    w.write(first + "\n")
                elif first != header:
                    raise SystemExit(
                        f"aws-cur-pull: error: header mismatch in {p.name}; a mid-period "
                        "schema change shifts columns silently. Refusing to join. "
                        "Pull the periods separately and normalize each.")
                for line in f:
                    w.write(line if line.endswith("\n") else line + "\n")
                    rows += 1
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--export-name", required=True)
    ap.add_argument("--period", required=True, help="YYYY-MM")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--local-dir", type=Path, help="already-synced parts; skip S3")
    ap.add_argument("--emit-cli", action="store_true")
    args = ap.parse_args()

    pfx = period_prefix(args.prefix, args.export_name, args.period)
    if args.emit_cli:
        print(emit_cli(args.bucket, pfx, "./cur-parts"))
        return
    if not args.out:
        raise SystemExit("aws-cur-pull: error: --out is required unless --emit-cli")

    if args.local_dir:
        workdir = args.local_dir
    else:
        if shutil.which("aws") is None:
            raise SystemExit("aws-cur-pull: error: the aws CLI is not on PATH; "
                             "use --emit-cli for the zero-access path")
        workdir = Path(tempfile.mkdtemp(prefix="cur-"))
        cmd = ["aws", "s3", "sync", f"s3://{args.bucket}/{pfx}", str(workdir),
               "--exclude", "*", "--include", "*.csv.gz"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"aws-cur-pull: aws s3 sync failed:\n{proc.stderr.strip()}")

    parts = sorted(workdir.rglob("*.csv.gz")) or sorted(workdir.rglob("*.csv"))
    rows = concatenate(parts, args.out)
    print(f"aws-cur-pull: {rows} rows from {len(parts)} part(s) -> {args.out}")


if __name__ == "__main__":
    main()
