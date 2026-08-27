"""aws-cur-pull tests: safe concatenation is the product."""

import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from aws_pull import concatenate, period_prefix, KNOWN_CUR2_COLUMNS

HEADER = "line_item_unblended_cost,line_item_usage_start_date\n"


def gz_part(path: Path, header: str, rows: list[str]) -> Path:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(header)
        f.writelines(rows)
    return path


def test_period_prefix_layout():
    assert (period_prefix("cur/", "daily", "2026-06")
            == "cur/daily/data/BILLING_PERIOD=2026-06/")


def test_concatenate_single_header(tmp_path):
    parts = [gz_part(tmp_path / "a.csv.gz", HEADER, ["1.0,2026-06-01\n"]),
             gz_part(tmp_path / "b.csv.gz", HEADER, ["2.0,2026-06-02\n", "3.0,2026-06-03\n"])]
    out = tmp_path / "out.csv"
    rows = concatenate(parts, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert rows == 3
    assert lines[0] == HEADER.strip()
    assert sum(1 for l in lines if l == HEADER.strip()) == 1


def test_header_mismatch_refuses_entirely(tmp_path):
    parts = [gz_part(tmp_path / "a.csv.gz", HEADER, ["1.0,2026-06-01\n"]),
             gz_part(tmp_path / "b.csv.gz", "different,header\n", ["x,y\n"])]
    with pytest.raises(SystemExit):
        concatenate(parts, tmp_path / "out.csv")


def test_parquet_is_named_error(tmp_path):
    p = tmp_path / "part.parquet"
    p.write_bytes(b"PAR1")
    with pytest.raises(SystemExit):
        concatenate([p], tmp_path / "out.csv")


def test_no_parts_is_error(tmp_path):
    with pytest.raises(SystemExit):
        concatenate([], tmp_path / "out.csv")


def test_seam_with_focus_normalize_mapping():
    """Every column the aws_cur2 mapping expects must be a known CUR2 column."""
    mapping = json.loads(
        (Path(__file__).parents[2] / "normalizers" / "focus-normalize" /
         "mappings" / "aws_cur2.json").read_text(encoding="utf-8"))
    known = set(KNOWN_CUR2_COLUMNS)
    for source_col in mapping["columns"]:
        assert source_col in known, f"mapping expects unknown CUR2 column {source_col!r}"
    for fp in mapping["fingerprint"]:
        assert fp in known
