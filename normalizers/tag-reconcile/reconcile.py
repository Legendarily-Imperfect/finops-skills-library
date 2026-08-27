#!/usr/bin/env python3
"""Canonicalize owner tags against one map; report every defect with its dollars.

One map, one canonicalizer: every other tool joins to this output rather than
re-deriving the rule. Case and whitespace recover automatically; anything else
recovers only through an explicit alias, because a wrong automatic match moves
real money between owners silently. Unknowns are reported, never guessed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

UNTAGGED = "(untagged)"


def load_map(path: Path) -> dict:
    m = json.loads(path.read_text(encoding="utf-8"))
    m.setdefault("tag_key", "owner")
    m.setdefault("aliases", {})
    m.setdefault("allowlist", [])
    # Precompute case/whitespace-insensitive lookups once.
    m["_canon_fold"] = {c.strip().lower(): c for c in m["canonical"]}
    m["_alias_fold"] = {a.strip().lower(): c for a, c in m["aliases"].items()}
    return m


def resolve(written: str | None, m: dict) -> tuple[str, str]:
    """Return (canonical_or_marker, defect_class). Exact canonical is 'ok'."""
    if written is None or written.strip() == "":
        return UNTAGGED, "untagged"
    if written in m["canonical"]:
        return written, "ok"
    folded = written.strip().lower()
    if folded in m["_canon_fold"]:
        return m["_canon_fold"][folded], "variant"
    if folded in m["_alias_fold"]:
        return m["_alias_fold"][folded], "alias"
    return written, "unknown"


def reconcile(rows: list[dict], m: dict) -> tuple[list[dict], dict]:
    """Annotate rows with x_owner_canonical; build the dollar-ranked defect report."""
    tag_key = m["tag_key"]
    allow = set(m["allowlist"])
    dollars: dict[tuple[str, str], Decimal] = defaultdict(Decimal)   # (class, written) -> $
    resources: dict[tuple[str, str], set] = defaultdict(set)
    total = ok_total = Decimal("0")

    for row in rows:
        try:
            tags = json.loads(row.get("Tags") or "{}")
        except json.JSONDecodeError:
            tags = {}
        written = tags.get(tag_key)
        canonical, cls = resolve(written, m)
        row["x_owner_canonical"] = canonical
        cost = Decimal(row.get("BilledCost") or "0")
        total += cost
        if cls == "ok" or (written in allow):
            ok_total += cost
            continue
        key = (cls, written if written is not None else "")
        dollars[key] += cost
        if row.get("ResourceName"):
            resources[key].add(row["ResourceName"])

    defects = sorted(
        ({"class": cls, "written": written,
          "canonical": resolve(written or None, m)[0] if cls in ("variant", "alias") else None,
          "dollars": format(amount, "f"),
          "resources": sorted(resources[(cls, written)])}
         for (cls, written), amount in dollars.items()),
        key=lambda d: Decimal(d["dollars"]), reverse=True)

    auto_recovered = sum(Decimal(d["dollars"]) for d in defects if d["class"] in ("variant", "alias"))
    report = {
        "total_dollars": format(total, "f"),
        "cleanly_owned_dollars": format(ok_total, "f"),
        "auto_recovered_dollars": format(auto_recovered, "f"),
        "coverage_pct_after_recovery": (
            format((ok_total + auto_recovered) / total * 100, ".1f") if total else "100.0"),
        "defects": defects,
    }
    return rows, report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--map", dest="map_path", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="write the input plus x_owner_canonical")
    ap.add_argument("--report", type=Path, help="write the defect report as JSON")
    args = ap.parse_args()

    m = load_map(args.map_path)
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    rows, report = reconcile(rows, m)

    if args.out:
        with args.out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header + ["x_owner_canonical"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    payload = json.dumps(report, indent=2)
    if args.report:
        args.report.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    if any(d["class"] in ("untagged", "unknown") for d in report["defects"]):
        sys.exit(1)  # actionable defects remain; automation should notice


if __name__ == "__main__":
    main()
