---
name: exec-brief
description: >-
  Turn analyzer outputs into a one-page leadership memo in the markdown dialect
  report-render consumes, so brief-to-PDF-or-deck is one more command. Use when someone
  says "summarize this for leadership", "monthly cost memo", "exec summary", "make this
  presentable", or at the end of any analysis chain. The discipline is inherited from the
  whole library: this tool READS pre-computed numbers from the analyzer JSON files it is
  given and never recomputes one, because a brief that re-derives a figure is a second
  implementation waiting to disagree with the first. Sections appear only for the inputs
  provided (showback, variance, anomalies, waste, tie-out), findings lead with dollars,
  and estimated figures keep their badges in front of leadership, where dropping them is
  most tempting and most costly.
---

# exec-brief

## Data Contract

**In:** any subset of `--showback`, `--variance`, `--anomalies`, `--waste`, `--tieout` (each the JSON file its analyzer wrote) plus `--title` and `--period`. **Out:** markdown to stdout or `--out brief.md`, in the `report-render` subset: `#` title, `::` metric cards, `##` sections, tables, callouts.

## Rules

- **Never recompute.** Every number in the brief is copied from an input file. A brief that re-derives a figure is a second implementation waiting to disagree with the first.
- **Cards first.** The top of the page is three to five `::` metrics drawn from whichever inputs exist (allocated total, variance, top anomaly, recoverable waste, tie-out verdict).
- **Badges survive.** Estimated figures say estimated in the memo. Dropping the badge in front of leadership is where it is most tempting and most costly.
- **Findings lead with dollars** and name an owner where the input has one.

## Usage

```powershell
python brief.py --title "June Cloud Costs" --period 2026-06 --showback sb.json --variance var.json --waste waste.json --out brief.md
python ..\..\output\report-render\render.py --in brief.md --out brief.html
python -m pytest -q
```

## Non-Goals

Analysis (upstream), commentary generation (the memo states findings; the narrative sentence is yours or your agent's, grounded per `agent-guardrails`), and layout (that is `report-render`).
