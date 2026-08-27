"""rightsize-on-peaks tests: the spiky-workload protection is the product."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from usage_stats import stats, recommend, percentile_nearest_rank, windowed_averages

STEADY = [48, 50, 52, 49, 51, 50, 47, 53, 50, 49] * 10          # ~50%, low CoV
SPIKY = [12, 10, 14, 11, 9, 13, 95, 96, 94, 12, 10, 11] * 10    # low avg, real peaks
IDLE = [3, 4, 2, 3, 5, 3, 4, 2, 3, 4] * 10


def test_percentile_nearest_rank_is_a_real_sample():
    values = list(range(1, 101))
    assert percentile_nearest_rank(values, 99) == 99
    assert percentile_nearest_rank(values, 95) in values


def test_windowed_average_smooths_single_spikes():
    series = [10] * 20 + [100] + [10] * 20
    assert max(windowed_averages(series, 5)) < 100  # one blip is not sustained demand


def test_spiky_workload_is_not_a_downsize_candidate():
    """The founding rule: 20% average with 95% peaks is correctly sized."""
    r = recommend(SPIKY, current=16, unit="vCPU")
    assert r["verdict"] == "correctly_sized"
    assert r["recommended"] == 16


def test_average_would_have_said_downsize():
    """Documents the failure mode this tool prevents."""
    s = stats(SPIKY)
    assert s["mean"] < 35          # an average-based sizer would slash this
    assert s["p99"] > 90           # and the peak says otherwise


def test_idle_workload_is_downsize_candidate():
    r = recommend(IDLE, current=16, unit="vCPU")
    assert r["verdict"] == "downsize_candidate"
    assert r["recommended"] < 16


def test_steady_workload_gets_thin_headroom_spiky_gets_thick():
    steady = recommend(STEADY, current=8, unit="vCPU")
    spiky = recommend(SPIKY, current=16, unit="vCPU")
    assert steady["headroom_pct"] < spiky["headroom_pct"]


def test_every_recommendation_is_badged_and_carries_stats():
    r = recommend(IDLE, current=16, unit="vCPU")
    assert r["badge"] == "estimated"
    assert set(r["stats"]) >= {"mean", "median", "p95", "p99", "max_window_avg", "min_window_avg", "cov"}


def test_empty_series_is_error():
    with pytest.raises(SystemExit):
        stats([])
