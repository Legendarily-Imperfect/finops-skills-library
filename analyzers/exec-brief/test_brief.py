"""exec-brief tests: the whole chain, sample to memo to render, numbers copied intact."""

import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from brief import build

LIB = Path(__file__).parents[2]
SAMPLE_DIR = LIB / "synthetic-data" / "sample"
for skill in ("analyzers/showback", "analyzers/waste-classify", "analyzers/anomaly-detect",
              "output/report-render"):
    sys.path.insert(0, str(LIB / skill))
from showback import showback  # noqa: E402
from classify import classify, DEFAULT_CONFIG  # noqa: E402
from detect import detect  # noqa: E402
from render import parse  # noqa: E402


def sample_rows():
    with (SAMPLE_DIR / "billing.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def full_brief():
    rows = sample_rows()
    return build("June Cloud Costs", "2026-06",
                 showback=showback(rows),
                 variance=None,
                 anomalies=detect(rows, by="resource"),
                 waste=classify(rows, DEFAULT_CONFIG),
                 tieout=None)


def test_cards_lead_the_page():
    md = full_brief()
    lines = md.splitlines()
    first_card = next(i for i, l in enumerate(lines) if l.startswith("::"))
    assert first_card < 6
    assert sum(1 for l in lines if l.startswith("::")) >= 3


def test_numbers_are_copied_not_recomputed():
    rows = sample_rows()
    sb = showback(rows)
    md = build("t", "p", sb, None, None, None, None)
    assert f"${sb['allocated_total']}" in md
    assert sb["owners"][0]["dollars"] in md


def test_estimated_badge_survives_into_the_memo():
    md = full_brief()
    assert "(est.)" in md or "estimate" in md.lower()


def test_renders_through_report_render():
    """The memo must parse into the exact block types render.py styles."""
    blocks = parse(full_brief())
    kinds = {b["type"] for b in blocks}
    assert {"heading", "metrics", "table", "list"} <= kinds


def test_sections_only_for_provided_inputs():
    md = build("t", "p", None, None, None, None, None)
    assert "## " not in md  # no inputs, no sections, no invented content
