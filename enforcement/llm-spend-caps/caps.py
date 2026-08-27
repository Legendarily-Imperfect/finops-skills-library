#!/usr/bin/env python3
"""Pooled LLM spend-cap enforcer: check before the call, record after it.

The only tool in this library that writes anything, and what it writes is
its own ledger (a local JSONL file), never a cloud resource. Vendor
agnostic: it never calls an LLM API; you wire `check` in front of your
calls and `record` behind them, whatever the provider.

The rules that make it an enforcer rather than a dashboard:

- FAIL CLOSED. A corrupt ledger line refuses the check; an enforcer that
  fails open on bad state is a dashboard with extra steps.
- Decimal money end to end. Config amounts are quoted strings; a bare
  JSON number in a cap is a fatal error, because floats corrupt money.
- Deny names its numbers: which cap, spent, cap, and the estimate that
  tipped it, so the denied caller can see the arithmetic.

Stated limitation (this tool is a work in progress): check and record are
two steps, so concurrent in-flight calls can overshoot a cap by the sum
of their estimates. Single-writer queues are exact; fan-out callers
should subtract a safety margin from the caps.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Quoted-string amounts only. A JSON number is fatal, not coerced."""
    if not isinstance(value, str):
        raise SystemExit(f"llm-spend-caps: fatal: amount {value!r} is a bare JSON number; "
                         "quote it as a string, floats corrupt money")
    try:
        return Decimal(value).quantize(CENT)
    except InvalidOperation:
        raise SystemExit(f"llm-spend-caps: fatal: {value!r} is not a money amount")


def load_config(path: str) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    out = {
        "pool_monthly_cap": money(cfg["pool_monthly_cap"]),
        "per_user_monthly_cap": money(cfg["per_user_monthly_cap"]),
        "user_overrides": {u: money(v) for u, v in cfg.get("user_overrides", {}).items()},
    }
    return out


def load_month(ledger_path: str, month: str) -> tuple[Decimal, dict[str, Decimal]]:
    """Sum the ledger for one month. A corrupt line REFUSES; it never skips."""
    pool = Decimal("0.00")
    per_user: dict[str, Decimal] = {}
    p = Path(ledger_path)
    if not p.exists():
        return pool, per_user
    for lineno, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            cost = money(entry["cost"])
            user = entry["user"]
            entry_month = entry["date"][:7]
        except (json.JSONDecodeError, KeyError, SystemExit):
            raise SystemExit(f"llm-spend-caps: fatal: ledger line {lineno} is corrupt; "
                             "refusing to enforce caps against unknown spend (fail closed)")
        if entry_month != month:
            continue
        pool += cost
        per_user[user] = per_user.get(user, Decimal("0.00")) + cost
    return pool, per_user


def user_cap(config: dict, user: str) -> Decimal:
    return config["user_overrides"].get(user, config["per_user_monthly_cap"])


def check(config: dict, ledger_path: str, user: str, estimate: Decimal, today: date) -> dict:
    month = today.isoformat()[:7]
    pool_spent, per_user = load_month(ledger_path, month)
    u_spent = per_user.get(user, Decimal("0.00"))
    u_cap = user_cap(config, user)
    p_cap = config["pool_monthly_cap"]

    if u_spent + estimate > u_cap:
        verdict = {"allow": False, "cap": "user", "user": user, "month": month,
                   "spent": str(u_spent), "limit": str(u_cap), "estimate": str(estimate),
                   "reason": f"user {user} at {u_spent} of {u_cap}; "
                             f"estimate {estimate} would breach the user cap"}
    elif pool_spent + estimate > p_cap:
        verdict = {"allow": False, "cap": "pool", "user": user, "month": month,
                   "spent": str(pool_spent), "limit": str(p_cap), "estimate": str(estimate),
                   "reason": f"pool at {pool_spent} of {p_cap}; "
                             f"estimate {estimate} would breach the pool cap"}
    else:
        verdict = {"allow": True, "user": user, "month": month,
                   "user_remaining": str(u_cap - u_spent - estimate),
                   "pool_remaining": str(p_cap - pool_spent - estimate)}
    return verdict


def record(ledger_path: str, user: str, cost: Decimal, today: date) -> dict:
    entry = {"date": today.isoformat(), "user": user, "cost": str(cost)}
    with open(ledger_path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def status(config: dict, ledger_path: str, today: date) -> dict:
    month = today.isoformat()[:7]
    pool_spent, per_user = load_month(ledger_path, month)
    return {
        "month": month,
        "pool": {"spent": str(pool_spent), "cap": str(config["pool_monthly_cap"]),
                 "remaining": str(config["pool_monthly_cap"] - pool_spent)},
        "users": {u: {"spent": str(s), "cap": str(user_cap(config, u)),
                      "remaining": str(user_cap(config, u) - s)}
                  for u, s in sorted(per_user.items())},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Pooled LLM spend-cap enforcer")
    ap.add_argument("action", choices=["check", "record", "status"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--user")
    ap.add_argument("--estimate", help="estimated cost of the call (check)")
    ap.add_argument("--cost", help="actual cost of the call (record)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible runs")
    args = ap.parse_args()

    config = load_config(args.config)
    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.action == "check":
        if not args.user or args.estimate is None:
            raise SystemExit("llm-spend-caps: check needs --user and --estimate")
        verdict = check(config, args.ledger, args.user, money(args.estimate), today)
        print(json.dumps(verdict, indent=2))
        sys.exit(0 if verdict["allow"] else 3)
    elif args.action == "record":
        if not args.user or args.cost is None:
            raise SystemExit("llm-spend-caps: record needs --user and --cost")
        print(json.dumps(record(args.ledger, args.user, money(args.cost), today)))
    else:
        print(json.dumps(status(config, args.ledger, today), indent=2))


if __name__ == "__main__":
    main()
