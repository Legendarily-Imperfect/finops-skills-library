---
name: sync-check
description: >-
  Confirm a data pipeline's change actually landed downstream, and block when it did not.
  Use before reconciling anything, before demoing a dashboard, or whenever someone asks
  "did the sync run", "is the app current", "why is the page showing last week", "did my
  fix land", "check the pipeline log". Feed it the pipeline or sync log and it blocks on
  three conditions: no successful sync since a cutoff you name, a write that skipped its
  clear step (the clear-then-write rule: append without clearing relabels orphan rows and
  double-counts), and a write into a closed period. The failure this tool is built against
  is a checker that recognizes nothing in the log and therefore reports a clean run:
  unrecognized input here FAILS LOUDLY, because a green check that parsed zero lines is
  the most dangerous output a verifier can produce. Run this before spend-tieout, always.
---

# sync-check

## Data Contract

**In:** a log file (or stdin) and `patterns.json` describing your pipeline's log lines as regexes with named groups:

```json
{
  "sync_start":    "sync starting",
  "sync_complete": "sync complete for (?P<period>\\d{4}-\\d{2}) at (?P<ts>[\\dT:\\-Z]+)",
  "clear":         "cleared period (?P<period>\\d{4}-\\d{2})",
  "write":         "wrote \\d+ rows into (?P<period>\\d{4}-\\d{2})"
}
```

A default patterns file ships for the common `clear/write/complete` shape; point `--patterns` at your own for your pipeline's phrasing.

**Out:** PASS or BLOCK per rule with the offending lines, JSON with `--json`. Exit 0 pass, 2 blocked, 3 nothing recognized.

## Block Rules

| Rule | Trigger | Why It Blocks |
|---|---|---|
| Stale | no `sync_complete` at or after `--since` | Reconciling a page showing last week proves nothing |
| Skipped clear | a `write` for a period with no prior `clear` in the same run | Clear-then-write is the upsert rule; append relabels orphans and double-counts |
| Closed period | a `write` whose period is before `--closed-before` | Closed periods are signed off; a write there silently rewrites history |
| Nothing recognized | zero lines matched any pattern | A checker that parsed nothing has verified nothing; exit 3, never 0 |

## Usage

```powershell
python check_sync.py --log pipeline.log --since 2026-08-25 --closed-before 2026-07
python check_sync.py --log pipeline.log --patterns my-patterns.json --json
python -m pytest -q
```

## Non-Goals

Running the sync, fixing the pipeline, or knowing your log format by magic: the patterns file is the contract, and writing it for your pipeline is the adaptation step.
