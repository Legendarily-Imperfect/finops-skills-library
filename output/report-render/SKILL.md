---
name: report-render
description: >-
  Render a report written in markdown to a print-ready Letter HTML page (print to PDF from
  any browser) or a 16:9 slide deck. Use when someone says "make this a PDF", "turn this
  into a deck", "client-ready version", "print this report", "slides for the monthly
  review", or an analyzer's output needs to leave the terminal. Structure drives layout,
  not a chosen template: headings split slides, lines shaped `:: label | value` become
  metric cards, tables and callouts style themselves, and long lists continue onto another
  slide rather than clipping. The palette lives in one JSON file, deliberately unbranded:
  swap palette.json for your colors and every artifact follows. The deck path needs
  python-pptx (the one named extra); the HTML path needs nothing beyond the baseline.
---

# report-render

## Data Contract

**In:** a markdown file using the supported subset: `#`/`##`/`###` headings, paragraphs, bullet and numbered lists, pipe tables, `>` callouts, `:: label | value` metric lines (consecutive ones group into a card row), `**bold**`, `*italic*`, `` `code` ``, links. **Out:** a single self-contained `.html` (Letter, print CSS, no external assets) or a `.pptx` (16:9).

**Palette:** `palette.json` beside the script: ink, accent, background, table header, callout, and font names. One file, every color; nothing is hardcoded in the renderers.

## Layout Rules

- **HTML:** `@page` Letter with margins; tables get the palette header row and alternating rows; callouts get the tinted box; metric cards render as a flex row. Page breaks avoid splitting a table row or a callout.
- **Deck:** the `#` title becomes the title slide; each `##` starts a slide; `###` bolds a run inside the slide. A slide that would overflow its body **continues onto a new slide titled with "(cont.)"** rather than shrinking text below readability or clipping, because a clipped list silently loses content and a 10pt list was never read.
- **Metric lines** (`:: MTD Spend | $1.2M`) become side-by-side cards on both paths: the deck's headline numbers and the PDF's stat band are the same source line.

## Usage

```powershell
python render.py --in report.md --out report.html
python render.py --in report.md --out report.pptx          # needs python-pptx
python render.py --in report.md --out report.html --palette my-palette.json
python -m pytest -q
```

## Prerequisites Beyond The Baseline

`pip install python-pptx` for the deck path only. HTML needs nothing.

## Non-Goals

Full CommonMark (the subset above is the contract), charts (render images upstream and reference them, or keep numbers in tables and cards), and PDF generation itself: browsers print the HTML to PDF better than any Python PDF library renders it.
