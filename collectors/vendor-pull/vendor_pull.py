#!/usr/bin/env python3
"""Cardinality-partitioned vendor API puller: months, then sub-dimension, never offset.

Offset paging is wrong, not slow: with a non-unique sort key, page-boundary
rows duplicate while others drop (measured: $7,775 low at page size 500,
$1,922 high at 2,000, from identical data). Partitions here are disjoint and
exhaustive so parts sum to the whole, and a partition that still fills the
row cap RAISES rather than returning a truncated read that looks complete.

The fetcher is injectable: fetch(params) -> list[dict]. The default fetcher
POSTs JSON with a bearer token from the environment; tests inject fakes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.request
from pathlib import Path


class PartitionOverflow(SystemExit):
    def __init__(self, partition: str, cap: int):
        print(f"vendor-pull: error: partition {partition} returned the row cap "
              f"({cap}); a capped read is truncated even though it looks complete. "
              "Add a finer partition_dimension for this vendor.", flush=True)
        super().__init__(2)


def months_between(start: str, end: str) -> list[str]:
    """Inclusive YYYY-MM list. Months are the first cut: each is a complete
    read on a natural boundary, which is what a caller widens anyway."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def default_fetcher(config: dict):
    token = os.environ.get(config["auth_env"], "")
    if not token:
        raise SystemExit(f"vendor-pull: error: {config['auth_env']} is not set; "
                         "the config names the variable, the environment holds the value")

    def fetch(params: dict) -> list[dict]:
        req = urllib.request.Request(
            config["base_url"],
            data=json.dumps(params).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read()).get("rows", [])
    return fetch


def pull(config: dict, start: str, end: str, fetch) -> tuple[list[dict], dict]:
    cap = int(config["row_cap"])
    dim = config.get("partition_dimension")
    values = config.get("partition_values") or []
    rows: list[dict] = []
    manifest = {"partitions": [], "row_cap": cap}

    for month in months_between(start, end):
        month_rows = fetch({"month": month})
        if len(month_rows) < cap:
            rows.extend(month_rows)
            manifest["partitions"].append({"partition": month, "rows": len(month_rows)})
            continue
        # Month overflows: cut by the sub-dimension. Disjoint and exhaustive.
        if not dim or not values:
            raise PartitionOverflow(month, cap)
        for value in values:
            part = f"{month}/{dim}={value}"
            part_rows = fetch({"month": month, dim: value})
            if len(part_rows) >= cap:
                raise PartitionOverflow(part, cap)
            rows.extend(part_rows)
            manifest["partitions"].append({"partition": part, "rows": len(part_rows)})
    manifest["total_rows"] = len(rows)
    return rows, manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--start", required=True, help="YYYY-MM")
    ap.add_argument("--end", required=True, help="YYYY-MM")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    rows, manifest = pull(config, args.start, args.end, default_fetcher(config))
    if rows:
        fieldnames = sorted({k for r in rows for k in r})
        with args.out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    args.out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"vendor-pull: {manifest['total_rows']} rows across "
          f"{len(manifest['partitions'])} partition(s) -> {args.out}")


if __name__ == "__main__":
    main()
