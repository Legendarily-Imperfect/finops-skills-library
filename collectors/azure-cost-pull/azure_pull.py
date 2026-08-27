#!/usr/bin/env python3
"""Pull the latest Azure Cost Management export run for a period.

Each export run writes a new file and old runs linger, so only the newest
file for the period is real: concatenating the folder double-counts every
earlier run. The chosen blob is printed so the choice is auditable. A
decimal-comma cost column refuses loudly rather than guessing locale.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

RUN_STAMP = re.compile(r"(\d{8}T\d{6}Z?|\d{14})")  # run timestamp in blob names/paths


def pick_latest(blob_names: list[str], period: str) -> str:
    """Newest run's blob for the period, by embedded run timestamp then name."""
    candidates = [b for b in blob_names
                  if period.replace("-", "") in b.replace("-", "") and b.endswith(".csv")]
    if not candidates:
        raise SystemExit(f"azure-cost-pull: error: no CSV blobs matching period {period}")

    def key(name: str) -> tuple:
        m = RUN_STAMP.search(name)
        return (m.group(1) if m else "", name)

    return max(candidates, key=key)


def sniff_decimal_comma(path: Path, cost_column: str = "CostInBillingCurrency",
                        sample: int = 50) -> bool:
    """True when the cost column reads as decimal-comma. Refusal beats guessing:
    a silent locale guess is a hundredfold error in either direction."""
    comma_hits = dot_hits = 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i >= sample:
                break
            v = (row.get(cost_column) or "").strip()
            if re.fullmatch(r"-?\d+,\d+", v):
                comma_hits += 1
            elif re.fullmatch(r"-?\d+(\.\d+)?", v):
                dot_hits += 1
    return comma_hits > dot_hits


def emit_cli(account: str, container: str, path: str, period: str) -> str:
    prefix = f"{path.strip('/')}/"
    return (
        f"az storage blob list --account-name {account} -c {container} "
        f"--prefix {prefix} --query [].name -o tsv\n"
        f"# pick the NEWEST blob for {period} (one file per run; old runs linger), then:\n"
        f"az storage blob download --account-name {account} -c {container} "
        f"-n <newest-blob> -f azure.csv --auth-mode login"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--period", required=True, help="YYYY-MM")
    ap.add_argument("--type", dest="export_type", choices=["actual", "amortized"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--emit-cli", action="store_true")
    args = ap.parse_args()

    if args.emit_cli:
        print(emit_cli(args.account, args.container, args.path, args.period))
        return
    if not args.out or not args.export_type:
        raise SystemExit("azure-cost-pull: error: --out and --type are required "
                         "unless --emit-cli (the export type changes the columns)")
    if shutil.which("az") is None:
        raise SystemExit("azure-cost-pull: error: the az CLI is not on PATH; "
                         "use --emit-cli for the zero-access path")

    listing = subprocess.run(
        ["az", "storage", "blob", "list", "--account-name", args.account,
         "-c", args.container, "--prefix", f"{args.path.strip('/')}/",
         "--query", "[].name", "-o", "tsv", "--auth-mode", "login"],
        capture_output=True, text=True)
    if listing.returncode != 0:
        raise SystemExit(f"azure-cost-pull: blob list failed:\n{listing.stderr.strip()}")
    chosen = pick_latest(listing.stdout.split(), args.period)
    print(f"azure-cost-pull: newest run for {args.period}: {chosen}", file=sys.stderr)

    dl = subprocess.run(
        ["az", "storage", "blob", "download", "--account-name", args.account,
         "-c", args.container, "-n", chosen, "-f", str(args.out), "--auth-mode", "login"],
        capture_output=True, text=True)
    if dl.returncode != 0:
        raise SystemExit(f"azure-cost-pull: download failed:\n{dl.stderr.strip()}")

    if sniff_decimal_comma(args.out):
        raise SystemExit(
            "azure-cost-pull: error: the cost column reads as decimal-comma "
            "(e.g. 12,50). Re-export with an invariant-culture schema or convert "
            "explicitly; refusing to guess locale.")
    print(f"azure-cost-pull: {args.out} (export type {args.export_type}; "
          f"run focus-normalize --mapping azure_cost next)")


if __name__ == "__main__":
    main()
