---
name: tag-reconcile
description: >-
  Map messy owner tags onto one canonical owner dimension and produce the ranked,
  dollar-sized defect list a person can act on. Use when someone asks "how much spend has
  no owner", "whose spend is this", "fix our tagging", "how bad is tag compliance", "why
  don't the showback numbers add up", or when two reports disagree because each canonicalized
  tags its own way. The one-map rule this skill enforces: there is exactly one owner map and
  one canonicalizer, and every tool joins to this output rather than re-deriving the mapping.
  Two implementations of an attribution rule eventually disagree, and when they do, a
  chargeback report and a developer's block contradict each other with no way to say which
  is right. Case and whitespace variants recover automatically; typos and renames recover
  only through an explicit alias in the map, and until aliased they are reported, never guessed.
---

# tag-reconcile

## Data Contract

**In:** a FOCUS CSV (Tags as a JSON object string, `owner` key by default) and `owner-map.json`:

```json
{
  "tag_key": "owner",
  "canonical": ["Atlas", "Borealis"],
  "aliases": {"delta-team": "Delta", "cascasde": "Cascade"},
  "allowlist": ["a-known-accepted-divergence"]
}
```

**Out:** a defect report (JSON to stdout or `--report out.json`) with coverage percent and defects grouped by class, each carrying total dollars and affected resources, ranked by dollars; and optionally `--out corrected.csv`, the input with an `x_owner_canonical` column added. The original Tags are never rewritten: provenance survives.

## Defect Classes

| Class | Meaning | Recovery |
|---|---|---|
| `untagged` | no owner key at all | needs a human; the map cannot invent ownership |
| `variant` | case or whitespace variant of a canonical | automatic |
| `alias` | matched an explicit alias | automatic, but flag renames upstream |
| `unknown` | an owner the map does not know | add an alias or a canonical; reported until then |

## Rules

- **Never guess.** An unknown owner is reported with its dollars, not fuzzy-matched. A wrong automatic match moves real money between owners silently.
- **Dollars rank the work.** A defect list ordered by row count buries the $40K unknown under a thousand $0.02 variants.
- **The allowlist keeps the report signal.** Known accepted divergences are excluded so every line in the report is actionable.

## Usage

```powershell
python reconcile.py --in focus.csv --map owner-map.json
python reconcile.py --in focus.csv --map owner-map.json --out corrected.csv --report defects.json
python -m pytest -q
```

## Non-Goals

Multi-key tag policy (env, app, cost-center) beyond the owner dimension in v1, and writing tags back to any cloud. This reconciles the data; fixing the source is governance work the report arms you for.
