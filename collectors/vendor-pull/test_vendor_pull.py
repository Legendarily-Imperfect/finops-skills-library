"""vendor-pull tests: partitioning is the product, truncation never ships."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from vendor_pull import months_between, pull, PartitionOverflow

CONFIG = {"row_cap": 100, "partition_dimension": "cloud",
          "partition_values": ["aws", "azure", "gcp"]}


def test_months_between_inclusive_and_year_crossing():
    assert months_between("2026-11", "2027-02") == ["2026-11", "2026-12", "2027-01", "2027-02"]
    assert months_between("2026-06", "2026-06") == ["2026-06"]


def test_small_months_fetch_whole():
    calls = []

    def fetch(params):
        calls.append(params)
        return [{"m": params["month"], "i": i} for i in range(10)]

    rows, manifest = pull(CONFIG, "2026-05", "2026-06", fetch)
    assert len(rows) == 20
    assert calls == [{"month": "2026-05"}, {"month": "2026-06"}]
    assert [p["partition"] for p in manifest["partitions"]] == ["2026-05", "2026-06"]


def test_overflowing_month_cuts_by_dimension_not_offset():
    def fetch(params):
        if "cloud" not in params:
            return [{"i": i} for i in range(100)]  # at cap: overflow signal
        return [{"cloud": params["cloud"], "i": i} for i in range(40)]

    rows, manifest = pull(CONFIG, "2026-06", "2026-06", fetch)
    assert len(rows) == 120  # 3 clouds x 40, parts sum to the whole
    parts = [p["partition"] for p in manifest["partitions"]]
    assert parts == ["2026-06/cloud=aws", "2026-06/cloud=azure", "2026-06/cloud=gcp"]


def test_partition_still_at_cap_raises_never_truncates():
    def fetch(params):
        return [{"i": i} for i in range(100)]  # everything overflows

    with pytest.raises(PartitionOverflow):
        pull(CONFIG, "2026-06", "2026-06", fetch)


def test_overflow_without_subdimension_raises():
    def fetch(params):
        return [{"i": i} for i in range(100)]

    with pytest.raises(PartitionOverflow):
        pull({"row_cap": 100}, "2026-06", "2026-06", fetch)


def test_manifest_proves_coverage():
    def fetch(params):
        return [{"i": i} for i in range(5)]

    rows, manifest = pull(CONFIG, "2026-04", "2026-06", fetch)
    assert manifest["total_rows"] == len(rows) == 15
    assert sum(p["rows"] for p in manifest["partitions"]) == manifest["total_rows"]
