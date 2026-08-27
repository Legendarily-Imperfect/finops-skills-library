---
name: llm-spend-caps
description: >-
  Pooled LLM spend-cap enforcer: check a call against monthly caps before it goes out,
  record the actual cost after it returns, deny with the arithmetic shown when a cap
  would be breached. Use when someone says "cap our AI spend", "budget per user for the
  LLM", "stop the agent from blowing the budget", "spend limits on API calls". Vendor
  agnostic: it never calls an LLM API; you wire check in front of your calls and record
  behind them, whatever the provider. The rules that make it an enforcer rather than a
  dashboard: it FAILS CLOSED (a corrupt ledger line refuses the check; failing open on
  bad state is a dashboard with extra steps); money is Decimal end to end with
  quoted-string amounts (a bare JSON number in a cap or ledger is fatal); and a deny
  names which cap, the spend, the limit, and the estimate that tipped it. This tool is a
  work in progress and says so: check and record are two steps, so concurrent in-flight
  calls can overshoot by the sum of their estimates; single-writer queues are exact,
  fan-out callers should shave a safety margin off the caps.
---

# llm-spend-caps

**Work in progress, offered as-is.** The core allow/deny logic is tested and exact; the concurrency limitation below is real and stated rather than hidden.

## Data Contract

**In:** `caps-config.json` (amounts as quoted strings; a bare number is fatal) and a local JSONL ledger this tool owns:

```json
{
  "pool_monthly_cap": "500.00",
  "per_user_monthly_cap": "50.00",
  "user_overrides": {"ci-bot": "200.00"}
}
```

**Out:** `check` prints a verdict and exits 0 (allow) or 3 (deny); `record` appends `{date, user, cost}`; `status` prints spent/cap/remaining for the pool and every user this month.

## Rules

- **Fail closed.** One corrupt ledger line and every check refuses until a human fixes it. Unknown spend cannot be enforced against.
- **Quoted-string money only**, in the config and in the ledger. `0.10` recorded three times sums to exactly `0.30`.
- **Deny shows its arithmetic**: cap type, spent, limit, estimate. A denial nobody can verify breeds cap-raising by frustration.
- **User cap checks before pool cap**, so one user cannot drain the pool and the denial blames the right limit.
- **Months roll over by calendar month** from the entry dates; nothing is deleted.

## Known Limitation

`check` then `record` is not atomic: N concurrent in-flight calls can overshoot a cap by the sum of their estimates. Route calls through a single-writer queue for exactness, or set caps with a margin. This is the honest version of a limitation most cap tools have and do not mention.

## Usage

```powershell
python caps.py check --config caps-config.json --ledger spend.jsonl --user alice --estimate 0.42
python caps.py record --config caps-config.json --ledger spend.jsonl --user alice --cost 0.38
python caps.py status --config caps-config.json --ledger spend.jsonl
python -m pytest -q
```

## Non-Goals

Calling any LLM API, estimating call cost (pair token counts with your rates; see `ai-spend`), multi-host shared state (the ledger is one local file), and authentication of callers.
