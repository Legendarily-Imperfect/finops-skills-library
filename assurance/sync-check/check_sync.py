#!/usr/bin/env python3
"""Verify a sync log: stale, skipped-clear, and closed-period writes all block.

The founding failure: a checker that recognizes nothing in the log and
therefore reports a clean run. Zero matched lines here exits 3, never 0,
because a green check that parsed nothing has verified nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

DEFAULT_PATTERNS = {
    "sync_complete": r"sync complete(?: for (?P<period>\d{4}-\d{2}))? at (?P<ts>[\dT:\-\.]+Z?)",
    "clear": r"clear(?:ed|ing) period (?P<period>\d{4}-\d{2})",
    "write": r"(?:wrote|writing) .* (?:into|for) period (?P<period>\d{4}-\d{2})",
}


def parse_ts(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def check(lines: list[str], patterns: dict[str, str],
          since: date | None, closed_before: str | None) -> dict:
    compiled = {name: re.compile(p, re.IGNORECASE) for name, p in patterns.items()}
    events: list[tuple[str, dict, str]] = []
    for line in lines:
        for name, rx in compiled.items():
            m = rx.search(line)
            if m:
                events.append((name, m.groupdict(), line.rstrip()))
                break

    blocks: list[dict] = []
    if not events:
        return {"recognized": 0, "verdict": "NOTHING_RECOGNIZED",
                "detail": "zero log lines matched any pattern; a green check that "
                          "parsed nothing has verified nothing"}

    # Stale: newest sync_complete timestamp must be >= --since.
    if since is not None:
        completes = [parse_ts(g.get("ts", "")) for n, g, _ in events if n == "sync_complete"]
        completes = [t for t in completes if t]
        newest = max(completes) if completes else None
        if newest is None or newest.date() < since:
            blocks.append({"rule": "stale",
                           "detail": f"no sync_complete at or after {since.isoformat()} "
                                     f"(newest: {newest.isoformat() if newest else 'none'})"})

    # Skipped clear: a write whose period saw no clear earlier in the log.
    cleared: set[str] = set()
    for name, groups, line in events:
        if name == "clear" and groups.get("period"):
            cleared.add(groups["period"])
        elif name == "write" and groups.get("period"):
            if groups["period"] not in cleared:
                blocks.append({"rule": "skipped_clear", "line": line,
                               "detail": f"write into {groups['period']} with no prior clear; "
                                         "append without clear relabels orphans and double-counts"})

    # Closed period: writes before the closed boundary.
    if closed_before is not None:
        for name, groups, line in events:
            if name == "write" and groups.get("period") and groups["period"] < closed_before:
                blocks.append({"rule": "closed_period", "line": line,
                               "detail": f"write into {groups['period']}, closed before {closed_before}"})

    return {"recognized": len(events),
            "verdict": "BLOCK" if blocks else "PASS",
            "blocks": blocks}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", type=Path, help="log file; omit to read stdin")
    ap.add_argument("--patterns", type=Path, help="patterns JSON; default common shape")
    ap.add_argument("--since", help="YYYY-MM-DD; newest sync must be at or after this")
    ap.add_argument("--closed-before", help="YYYY-MM; writes into earlier periods block")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lines = (args.log.read_text(encoding="utf-8", errors="replace").splitlines()
             if args.log else sys.stdin.read().splitlines())
    patterns = (json.loads(args.patterns.read_text(encoding="utf-8"))
                if args.patterns else DEFAULT_PATTERNS)
    since = date.fromisoformat(args.since) if args.since else None
    result = check(lines, patterns, since, args.closed_before)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"sync-check: {result['verdict']} ({result['recognized']} lines recognized)")
        for b in result.get("blocks", []):
            print(f"  BLOCK [{b['rule']}] {b['detail']}")
        if result["verdict"] == "NOTHING_RECOGNIZED":
            print(f"  {result['detail']}")
    sys.exit({"PASS": 0, "BLOCK": 2, "NOTHING_RECOGNIZED": 3}[result["verdict"]])


if __name__ == "__main__":
    main()
