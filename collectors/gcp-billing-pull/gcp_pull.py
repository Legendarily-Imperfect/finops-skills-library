#!/usr/bin/env python3
"""Pull the GCP BigQuery billing export with correct partition discipline.

The export table is partitioned on ingestion time. A correct query filters both
_PARTITIONTIME (prunes partitions, controls scan cost) and usage_start_time
(the correct predicate), because a correction to old usage lands in a new
partition. Windows are rebuilt, never appended, for the same reason.

--emit-sql prints the query and exits, so the skill is useful with no GCP
access at all. Live mode shells out to the bq CLI rather than importing a
client library, keeping the baseline dependency-free.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# Padding on the partition filter, both sides: corrections to usage inside the
# window arrive in partitions ingested after it, and rows for the window's
# first day can sit in partitions ingested slightly before it.
PARTITION_PAD_DAYS = 2


def build_sql(project: str, dataset: str, table: str, start: date, end: date) -> str:
    """SQL for [start, end] inclusive by usage day, flattened for focus-normalize."""
    if end < start:
        raise SystemExit("gcp-billing-pull: error: end date precedes start date")
    p_start = (start - timedelta(days=PARTITION_PAD_DAYS)).isoformat()
    p_end = (end + timedelta(days=1 + PARTITION_PAD_DAYS)).isoformat()
    u_start, u_end = start.isoformat(), (end + timedelta(days=1)).isoformat()
    return f"""\
SELECT
  billing_account_id,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', usage_start_time) AS usage_start_time,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', usage_end_time)   AS usage_end_time,
  CAST(cost AS STRING)                                     AS cost,
  currency,
  service.description                                      AS service_description,
  sku.description                                          AS sku_description,
  sku.id                                                   AS sku_id,
  project.id                                               AS project_id,
  project.name                                             AS project_name,
  location.region                                          AS location_region,
  resource.name                                            AS resource_name,
  resource.global_name                                     AS resource_global_name,
  CAST(usage.amount AS STRING)                             AS usage_amount,
  usage.unit                                               AS usage_unit,
  TO_JSON_STRING(labels)                                   AS labels
FROM `{project}.{dataset}.{table}`
WHERE _PARTITIONTIME >= TIMESTAMP('{p_start}')
  AND _PARTITIONTIME <  TIMESTAMP('{p_end}')
  AND usage_start_time >= TIMESTAMP('{u_start}')
  AND usage_start_time <  TIMESTAMP('{u_end}')
"""


def resolve_window(days: int | None, start: str | None, end: str | None,
                   today: date | None = None) -> tuple[date, date]:
    """Trailing window ends yesterday: the current day's billing is partial and
    a partial day reads as a decline to every trend tool downstream."""
    today = today or date.today()
    if start and end:
        return date.fromisoformat(start), date.fromisoformat(end)
    if start or end:
        raise SystemExit("gcp-billing-pull: error: pass both --start and --end, or neither")
    n = days if days is not None else 10
    end_d = today - timedelta(days=1)
    return end_d - timedelta(days=n - 1), end_d


def run_bq(sql: str, project: str, out: Path) -> None:
    bq = shutil.which("bq")
    if bq is None:
        raise SystemExit(
            "gcp-billing-pull: error: the bq CLI is not on PATH. Install the Google "
            "Cloud SDK and run gcloud auth login, or use --emit-sql and paste the "
            "query into the BigQuery console instead."
        )
    cmd = [bq, "query", f"--project_id={project}", "--use_legacy_sql=false",
           "--format=csv", "--max_rows=10000000", sql]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"gcp-billing-pull: bq failed:\n{proc.stderr.strip()}")
    out.write_text(proc.stdout, encoding="utf-8")
    rows = max(0, proc.stdout.count("\n") - 1)
    print(f"gcp-billing-pull: {rows} rows -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--days", type=int, help="trailing window ending yesterday (default 10)")
    ap.add_argument("--start", help="YYYY-MM-DD, requires --end")
    ap.add_argument("--end", help="YYYY-MM-DD, requires --start")
    ap.add_argument("--out", type=Path, help="CSV destination (required unless --emit-sql)")
    ap.add_argument("--emit-sql", action="store_true", help="print the SQL and exit")
    args = ap.parse_args()

    start, end = resolve_window(args.days, args.start, args.end)
    sql = build_sql(args.project, args.dataset, args.table, start, end)
    if args.emit_sql:
        print(sql)
        return
    if not args.out:
        raise SystemExit("gcp-billing-pull: error: --out is required unless --emit-sql")
    run_bq(sql, args.project, args.out)


if __name__ == "__main__":
    main()
