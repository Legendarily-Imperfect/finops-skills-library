---
name: focus-normalize
description: >-
  Convert a cloud billing export into FOCUS columns so every downstream tool reads one
  shape. Use when you have an AWS CUR (Data Exports v2), an Azure Cost Management export,
  a GCP BigQuery billing export, or any provider CSV and you need it "in FOCUS", "normalized",
  "standardized", "converted to a common schema", or ready for showback, variance, tie-out,
  or any analyzer in this library. Also use when someone says "make these exports comparable",
  "merge AWS and Azure spend", or "one file for all clouds". Mappings are data files, not code:
  add a provider by writing a JSON mapping, not by editing the script. Unknown source columns
  are preserved under an x_src_ prefix, never dropped. This tool does not validate the result;
  that is focus-conform's job, and the two are designed to run back to back.
---

# focus-normalize

## Data Contract

**In:** a CSV export from a provider, plus a mapping (named with `--mapping`, or auto-detected by column fingerprint). Ships with mappings for `aws_cur2`, `azure_cost`, `gcp_billing`, and `focus_passthrough`.

**Out:** a CSV carrying the FOCUS 1.0 core columns this library standardizes on (see `FOCUS_COLUMNS` in `normalize.py`), in fixed order. Source columns with no FOCUS home are preserved as `x_src_<original>`. Money is re-rendered as plain decimal strings via `Decimal`; a value that cannot parse is an error naming the row and column, never a silent zero.

## Rules That Are Not Obvious

- **Unknown columns are kept, not dropped.** Dropping is how provenance dies. `x_src_` keeps the original reachable for audit without polluting the FOCUS namespace.
- **Never `int()`, never `float()` on money.** Provider exports mix dollars-as-strings and fractional cents; `Decimal` end to end, rendered with no scientific notation.
- **Tags normalize to a JSON object string with sorted keys.** AWS `resource_tags_user_*` columns fold in; Azure `Tags` JSON passes through parsed and re-sorted; GCP `labels` JSON is re-keyed. Sorted keys make diffs and tests stable.
- **The mapping is the interface.** Each mapping JSON declares `fingerprint` (columns whose presence identifies the source), `columns` (source to FOCUS), `tag_columns` or `tag_json_column`, and `constants` (values the source cannot supply, like `ProviderName`). To support a new source, write a mapping and run `focus-conform` on the output; if it passes, you are done.

## Usage

```powershell
python normalize.py --in export.csv --out focus.csv                # auto-detect
python normalize.py --in export.csv --out focus.csv --mapping gcp_billing
python -m pytest -q
```

## Failure Modes

- Ambiguous or failed auto-detection: exits 2 naming the fingerprints tried; pass `--mapping`.
- Unparseable money: exits 2 with row number, column, and offending value.
- A mapping naming a source column the file lacks: exits 2 listing the missing columns, because a partial normalize looks exactly like a complete one and is worse than none.

## Non-Goals

Currency conversion, amortization math, credit reallocation, and validation. Validation is `focus-conform`; run it on every output of this tool.
