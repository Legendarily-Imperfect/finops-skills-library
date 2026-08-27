#!/usr/bin/env python3
"""Pull per-user LLM token usage from a Prometheus-compatible store, correctly.

The four rules that make this correct are in the SKILL.md with their
measurements; in code they are: sum_over_time (delta temporality), quoted
dotted names, hourly step with a matching [1h] window starting at the first
01:00, and pre-zeroed buckets so an idle hour is a zero, not a gap.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_HOURS = 7 * 24

# One model, several spellings: dated, @-versioned, bracketed, bare.
MODEL_FAMILY_RULES = [
    (re.compile(r"^(?P<fam>[a-z]+(?:-[a-z]+)*?-\d+(?:-\d+)?)[@\-\[]?"), "fam"),
]


def model_family(raw: str) -> str:
    """claude-opus-5[1m], claude-haiku-4-5-20251001, claude-haiku-4-5@20251001,
    and the bare name all collapse to their family; raw stays beside it."""
    name = raw.strip().lower()
    name = re.sub(r"\[[^\]]*\]$", "", name)          # trailing [variant]
    name = re.sub(r"@[\w\-\.]+$", "", name)           # @date/version
    name = re.sub(r"-(20\d{6}|20\d{2}-\d{2}-\d{2})$", "", name)  # trailing date
    return name or raw


def build_promql(metric: str, user: str | None = None) -> str:
    """Quoted __name__ selector (the metric has dots), sum_over_time, hourly window."""
    matchers = [f'__name__="{metric}"']
    if user:
        matchers.append(f'"user.email"="{user}"')
    selector = "{" + ", ".join(matchers) + "}"
    return f'sum by ("user.email", "model") (sum_over_time({selector}[1h]))'


def bucket_starts(end_utc: datetime, hours: int) -> list[datetime]:
    """Hourly points; a point at T covers (T-1h, T], so the earliest point for a
    window is the first 01:00-style boundary AFTER its start, not its midnight."""
    top = end_utc.replace(minute=0, second=0, microsecond=0)
    return [top - timedelta(hours=i) for i in range(hours - 1, -1, -1)]


def prezeroed(points: dict[tuple[str, str, datetime], float],
              buckets: list[datetime], keys: set[tuple[str, str]]) -> list[dict]:
    """Every (user, model, bucket) present: an idle hour is a zero, not a gap."""
    rows = []
    for user, model in sorted(keys):
        for b in buckets:
            rows.append({
                "bucket_start": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "user": user,
                "model_raw": model,
                "model_family": model_family(model),
                "tokens": int(points.get((user, model, b), 0)),
            })
    return rows


def query_range(endpoint: str, promql: str, start: datetime, end: datetime) -> list[dict]:
    params = urllib.parse.urlencode({
        "query": promql,
        "start": start.timestamp(), "end": end.timestamp(), "step": "3600",
    })
    with urllib.request.urlopen(f"{endpoint}/api/v1/query_range?{params}",
                                timeout=60) as resp:
        return json.loads(resp.read())["data"]["result"]


def collect(series: list[dict], buckets: list[datetime]) -> list[dict]:
    points: dict[tuple[str, str, datetime], float] = {}
    keys: set[tuple[str, str]] = set()
    bucket_set = set(buckets)
    for s in series:
        user = s["metric"].get("user.email", "(unknown)")
        model = s["metric"].get("model", "(unknown)")
        keys.add((user, model))
        for ts, value in s.get("values", []):
            t = datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)
            if t in bucket_set:
                points[(user, model, t)] = points.get((user, model, t), 0.0) + float(value)
    return prezeroed(points, buckets, keys)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--metric", required=True)
    ap.add_argument("--days", type=int)
    ap.add_argument("--hours", type=int)
    ap.add_argument("--user")
    ap.add_argument("--endpoint")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--emit-promql", action="store_true")
    args = ap.parse_args()

    if args.days and args.hours:
        raise SystemExit("otel-token-pull: error: pass --days OR --hours, not both; "
                         "they are alternatives feeding one range")
    hours = (args.days or 0) * 24 or (args.hours or 24)
    if hours > MAX_HOURS:
        raise SystemExit(f"otel-token-pull: error: window capped at {MAX_HOURS} hours")

    promql = build_promql(args.metric, args.user)
    if args.emit_promql:
        print(promql)
        return
    if not args.endpoint or not args.out:
        raise SystemExit("otel-token-pull: error: --endpoint and --out are required "
                         "unless --emit-promql")

    now = datetime.utcnow()
    buckets = bucket_starts(now, hours)
    series = query_range(args.endpoint, promql, buckets[0], buckets[-1])
    rows = collect(series, buckets)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["bucket_start", "user", "model_raw",
                                          "model_family", "tokens"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"otel-token-pull: {len(rows)} bucket rows -> {args.out}")


if __name__ == "__main__":
    main()
