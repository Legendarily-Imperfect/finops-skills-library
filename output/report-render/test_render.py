"""report-render tests: parser fidelity, palette injection, deck continuation."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from render import parse, render_html, inline_html, slide_plan, strip_inline

PALETTE = json.loads((Path(__file__).parent / "palette.json").read_text(encoding="utf-8"))

DOC = """# Monthly Cost Report

A one-line subtitle paragraph.

## Headline Numbers

:: MTD Spend | $1.2M
:: vs Budget | -3.4%
:: Waste Identified | $86K

## Findings

> **Note:** every figure below is badged billing or estimated.

- First finding with **bold** and a [link](https://example.com)
- Second finding
- Third finding

| Owner | Spend | Delta |
|---|---|---|
| Atlas | $400K | +2% |
| Cascade | $310K | -1% |
"""


def test_parse_block_types_in_order():
    kinds = [b["type"] for b in parse(DOC)]
    assert kinds == ["heading", "para", "heading", "metrics", "heading",
                     "callout", "list", "table"]


def test_metric_lines_group_into_one_block():
    metrics = [b for b in parse(DOC) if b["type"] == "metrics"][0]
    assert [m["label"] for m in metrics["items"]] == ["MTD Spend", "vs Budget", "Waste Identified"]
    assert metrics["items"][0]["value"] == "$1.2M"


def test_table_separator_row_dropped():
    table = [b for b in parse(DOC) if b["type"] == "table"][0]
    assert table["headers"] == ["Owner", "Spend", "Delta"]
    assert len(table["rows"]) == 2


def test_inline_escapes_before_formatting():
    out = inline_html("**a<b** and `x<y`")
    assert "<strong>a&lt;b</strong>" in out and "<code>x&lt;y</code>" in out


def test_html_uses_palette_not_hardcoded_colors():
    html_out = render_html(parse(DOC), PALETTE, "t")
    assert PALETTE["accent"] in html_out
    assert PALETTE["table_header_bg"] in html_out
    assert "@page" in html_out and "Letter" in html_out


def test_html_renders_all_structures():
    html_out = render_html(parse(DOC), PALETTE, "t")
    for needle in ('class="metrics"', 'class="callout"', "<table>", "<li>",
                   '<a href="https://example.com">'):
        assert needle in html_out


def test_slide_plan_title_and_sections():
    plan = slide_plan(parse(DOC))
    assert plan[0]["kind"] == "title" and plan[0]["title"] == "Monthly Cost Report"
    assert plan[0]["subtitle"] == "A one-line subtitle paragraph."
    titles = [s["title"] for s in plan[1:]]
    assert titles == ["Headline Numbers", "Findings"]


def test_long_list_continues_instead_of_clipping():
    md = "# T\n\n## Big Section\n\n" + "\n".join(f"- item {i}" for i in range(30))
    plan = slide_plan(parse(md))
    conts = [s for s in plan if s.get("title", "").endswith("(cont.)")]
    assert conts, "a 30-item list must continue onto further slides"
    total_items = sum(len(b["items"]) for s in plan if s["kind"] == "content"
                      for b in s["blocks"] if b["type"] == "list")
    assert total_items == 30, "continuation must not drop items"


def test_strip_inline_keeps_link_text():
    assert strip_inline("see [the report](https://x) **now**") == "see the report now"


def test_pptx_end_to_end(tmp_path):
    pptx = pytest.importorskip("pptx")
    from render import render_pptx
    out = tmp_path / "deck.pptx"
    render_pptx(parse(DOC), PALETTE, out)
    prs = pptx.Presentation(str(out))
    assert len(prs.slides) == 3  # title + two sections
    assert prs.slide_width.inches == pytest.approx(13.333, abs=0.01)


def test_html_cli(tmp_path):
    import subprocess
    src = tmp_path / "r.md"; src.write_text(DOC, encoding="utf-8")
    out = tmp_path / "r.html"
    proc = subprocess.run([sys.executable, str(Path(__file__).parent / "render.py"),
                           "--in", str(src), "--out", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert out.exists() and "Monthly Cost Report" in out.read_text(encoding="utf-8")
