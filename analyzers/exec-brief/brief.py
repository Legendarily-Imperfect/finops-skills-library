#!/usr/bin/env python3
"""Assemble a leadership memo from analyzer outputs; copy numbers, never recompute.

Every figure here is read from an input JSON. A brief that re-derives a figure
is a second implementation waiting to disagree with the first. Output is the
report-render markdown subset, so PDF or deck is one more command.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path


def load(path: Path | None) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def build(title: str, period: str, showback: dict | None, variance: dict | None,
          anomalies: dict | None, waste: dict | None, tieout: dict | None) -> str:
    lines: list[str] = [f"# {title}", "", f"Period: {period}. Figures copied from the "
                        "named analyses; estimated figures are badged.", ""]

    cards: list[str] = []
    if showback:
        cards.append(f":: Allocated Spend | ${showback['allocated_total']}")
        cards.append(f":: Tag Coverage | {showback['coverage_pct']}%")
    if variance:
        cards.append(f":: Variance vs Budget | ${variance['totals']['variance']}")
    if waste:
        cards.append(f":: Recoverable Waste (est.) | ${waste['total_recoverable_dollars']}")
    if tieout:
        verdicts = {c["verdict"] for c in tieout["comparisons"]}
        cards.append(f":: Tie-Out | {'TIES' if verdicts == {'tie'} else 'GAP'}")
    lines += cards[:5] + [""]

    if variance:
        lines += ["## Budget Variance", ""]
        over = [e for e in variance["by_owner"] if e["status"] == "over"][:5]
        if over:
            lines += ["| Owner | Actual | Budget | Variance |", "|---|---|---|---|"]
            lines += [f"| {e['owner']} | ${e['actual']} | ${e['budget']} | ${e['variance']} |"
                      for e in over]
        else:
            lines += ["No owner is over budget this period."]
        no_budget = [e["owner"] for e in variance["by_owner"] if e["status"] == "no_budget"]
        if no_budget:
            lines += ["", f"> **Note:** spend with no budget assigned: {', '.join(no_budget)}."]
        lines += [""]

    if anomalies and anomalies.get("hits"):
        lines += ["## Anomalies", ""]
        for h in anomalies["hits"][:3]:
            lines += [f"- {h['series']} on {h['date']}: ${h['actual']} "
                      f"({h['multiple']}x its average; excess ${h['excess_dollars']})"]
        lines += [""]

    if waste and waste.get("classes"):
        lines += ["## Waste (Estimated Recovery)", "",
                  "| Class | Billed | Recoverable (est.) | Rate Assumed |", "|---|---|---|---|"]
        for name, c in waste["classes"].items():
            lines += [f"| {name} | ${c['billed_dollars']} | ${c['recoverable_dollars']} "
                      f"| {c['recovery_rate_assumed']} |"]
        lines += ["", "> Recoverable figures are estimates under the stated rates, "
                  "not commitments.", ""]

    if showback:
        lines += ["## Spend By Owner", "", "| Owner | Dollars | Share |", "|---|---|---|"]
        for o in showback["owners"][:8]:
            lines += [f"| {o['owner']} | ${o['dollars']} | {o['share_pct']}% |"]
        lines += [""]

    if tieout:
        gaps = [c for c in tieout["comparisons"] if c["verdict"] == "gap"]
        if gaps:
            lines += ["## Tie-Out", ""]
            for g in gaps:
                lines += [f"> **Gap:** {g['legs']}: difference ${g['difference']}. "
                          "Candidate causes are in the tie-out report."]
            lines += [""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--title", required=True)
    ap.add_argument("--period", required=True)
    for name in ("showback", "variance", "anomalies", "waste", "tieout"):
        ap.add_argument(f"--{name}", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    md = build(args.title, args.period, load(args.showback), load(args.variance),
               load(args.anomalies), load(args.waste), load(args.tieout))
    if args.out:
        args.out.write_text(md, encoding="utf-8")
        print(f"exec-brief: {args.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
