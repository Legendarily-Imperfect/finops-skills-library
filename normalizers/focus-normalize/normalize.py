#!/usr/bin/env python3
"""Normalize a provider billing export into FOCUS columns.

Mappings are data files in ./mappings, not code. Each declares:
  fingerprint      - source columns whose joint presence identifies the format
  columns          - {source_column: FOCUS_column}
  money_columns    - FOCUS columns to re-render via Decimal (subset of columns' values)
  tag_json_column  - a source column already holding a JSON tag object (optional)
  tag_prefix       - fold source columns sharing this prefix into Tags (optional)
  constants        - {FOCUS_column: value} the source cannot supply

Unknown source columns are preserved as x_src_<name>, never dropped: dropping
is how provenance dies. Money goes through Decimal and is rendered plain; a
value that cannot parse is a named error, never a silent zero. Partial output
is worse than none, so missing mapped columns abort before any row is written.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

FOCUS_COLUMNS = [
    "BillingAccountId", "BillingAccountName", "SubAccountId", "SubAccountName",
    "BillingPeriodStart", "BillingPeriodEnd", "ChargePeriodStart", "ChargePeriodEnd",
    "BilledCost", "EffectiveCost", "ListCost", "ContractedCost", "BillingCurrency",
    "ChargeCategory", "ChargeDescription",
    "CommitmentDiscountId", "CommitmentDiscountStatus",
    "ProviderName", "PublisherName", "InvoiceIssuerName",
    "ServiceName", "ServiceCategory",
    "ResourceId", "ResourceName", "ResourceType",
    "RegionId", "RegionName",
    "ConsumedQuantity", "ConsumedUnit", "PricingQuantity", "PricingUnit",
    "SkuId", "SkuPriceId", "Tags",
]

MAPPINGS_DIR = Path(__file__).parent / "mappings"


class NormalizeError(SystemExit):
    def __init__(self, message: str):
        print(f"focus-normalize: error: {message}", file=sys.stderr)
        super().__init__(2)


def load_mappings() -> dict[str, dict]:
    out = {}
    for path in sorted(MAPPINGS_DIR.glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


def detect_mapping(header: list[str], mappings: dict[str, dict]) -> str:
    """Pick the mapping whose full fingerprint is present. Exactly one must match."""
    cols = set(header)
    hits = [name for name, m in mappings.items() if set(m["fingerprint"]).issubset(cols)]
    if len(hits) == 1:
        return hits[0]
    tried = {name: m["fingerprint"] for name, m in mappings.items()}
    kind = "ambiguous" if hits else "failed"
    raise NormalizeError(
        f"auto-detection {kind} (matches: {hits or 'none'}); pass --mapping. "
        f"Fingerprints tried: {json.dumps(tried)}"
    )


def plain_money(value: str, row_num: int, col: str) -> str:
    """Re-render money via Decimal; empty stays empty; garbage is a named error."""
    s = (value or "").strip()
    if s == "":
        return ""
    try:
        return format(Decimal(s), "f")
    except InvalidOperation:
        raise NormalizeError(f"unparseable money at row {row_num}, column {col!r}: {value!r}")


def normalize_rows(rows: list[dict], header: list[str], mapping: dict) -> list[dict]:
    colmap: dict[str, str] = mapping["columns"]
    missing = [src for src in colmap if src not in header]
    if missing:
        raise NormalizeError(
            f"mapping names source columns the file lacks: {missing}. "
            "A partial normalize looks complete; refusing to write any rows."
        )
    money_cols = set(mapping.get("money_columns", []))
    tag_json_column = mapping.get("tag_json_column")
    tag_prefix = mapping.get("tag_prefix")
    constants: dict[str, str] = mapping.get("constants", {})
    mapped_sources = set(colmap) | ({tag_json_column} if tag_json_column else set())

    out = []
    for i, row in enumerate(rows, start=2):  # header is line 1
        rec = {c: "" for c in FOCUS_COLUMNS}
        rec.update(constants)
        for src, dst in colmap.items():
            rec[dst] = row.get(src, "") or ""

        tags: dict[str, str] = {}
        if tag_json_column:
            raw = (row.get(tag_json_column) or "").strip()
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    raise NormalizeError(f"invalid tag JSON at row {i}, column {tag_json_column!r}")
                if isinstance(parsed, dict):
                    tags.update({str(k): str(v) for k, v in parsed.items()})
                elif isinstance(parsed, list):  # GCP labels: [{"key":..,"value":..}]
                    for item in parsed:
                        tags[str(item.get("key", ""))] = str(item.get("value", ""))
        if tag_prefix:
            for src in header:
                if src.startswith(tag_prefix) and (row.get(src) or "").strip():
                    tags[src[len(tag_prefix):]] = row[src].strip()
                    mapped_sources.add(src)
        rec["Tags"] = json.dumps(tags, sort_keys=True)

        for col in money_cols:
            rec[col] = plain_money(rec[col], i, col)

        for src in header:  # preserve everything unmapped
            if src not in mapped_sources and not (tag_prefix and src.startswith(tag_prefix)):
                rec[f"x_src_{src}"] = row.get(src, "") or ""
        out.append(rec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="dst", required=True, type=Path)
    ap.add_argument("--mapping", choices=sorted(m.stem for m in MAPPINGS_DIR.glob("*.json")))
    args = ap.parse_args()

    mappings = load_mappings()
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    name = args.mapping or detect_mapping(header, mappings)
    out_rows = normalize_rows(rows, header, mappings[name])

    extra = sorted({k for r in out_rows for k in r} - set(FOCUS_COLUMNS))
    fieldnames = FOCUS_COLUMNS + extra
    with args.dst.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"focus-normalize: {len(out_rows)} rows via mapping {name!r} -> {args.dst} "
          f"({len(extra)} preserved x_src_ columns)")


if __name__ == "__main__":
    main()
