#!/usr/bin/env python3
"""Render report markdown to print-ready Letter HTML or a 16:9 deck.

Structure drives layout: headings split slides, ':: label | value' lines
become metric cards, tables and callouts style themselves, and long lists
continue onto a new slide rather than clipping, because a clipped list
silently loses content. Every color comes from palette.json; nothing is
hardcoded in the renderers, so a palette swap rebrands every artifact.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

PALETTE_PATH = Path(__file__).parent / "palette.json"
DECK_BODY_LINES = 11  # bullets+paragraph lines per slide before continuation


# --------------------------- document model --------------------------------

def parse(md: str) -> list[dict]:
    """Markdown subset -> block list. Consecutive metric lines group into one card row."""
    blocks: list[dict] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append({"type": "heading", "level": min(level, 3),
                           "text": stripped[level:].strip()})
            i += 1
        elif stripped.startswith("::"):
            metrics = []
            while i < len(lines) and lines[i].strip().startswith("::"):
                body = lines[i].strip()[2:]
                label, _, value = body.partition("|")
                metrics.append({"label": label.strip(), "value": value.strip()})
                i += 1
            blocks.append({"type": "metrics", "items": metrics})
        elif stripped.startswith(">"):
            parts = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                parts.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append({"type": "callout", "text": " ".join(p for p in parts if p)})
        elif stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):  # skip separator
                    rows.append(cells)
                i += 1
            blocks.append({"type": "table", "headers": rows[0], "rows": rows[1:]})
        elif re.match(r"^(\-|\*|\d+\.)\s+", stripped):
            ordered = bool(re.match(r"^\d+\.", stripped))
            items = []
            while i < len(lines) and re.match(r"^(\-|\*|\d+\.)\s+", lines[i].strip()):
                items.append(re.sub(r"^(\-|\*|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            blocks.append({"type": "list", "ordered": ordered, "items": items})
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"^(#|::|>|\||\-|\*|\d+\.)", lines[i].strip()):
                para.append(lines[i].strip())
                i += 1
            blocks.append({"type": "para", "text": " ".join(para)})
    return blocks


def inline_html(text: str) -> str:
    """Escape, then apply the inline subset. Order matters: escape first."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return out


def strip_inline(text: str) -> str:
    """Plain text for deck runs: markdown markers removed, links keep their text."""
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    return re.sub(r"[*`]", "", out)


# --------------------------- HTML renderer ---------------------------------

def render_html(blocks: list[dict], palette: dict, title: str) -> str:
    p = palette
    parts: list[str] = []
    for b in blocks:
        if b["type"] == "heading":
            parts.append(f"<h{b['level']}>{inline_html(b['text'])}</h{b['level']}>")
        elif b["type"] == "para":
            parts.append(f"<p>{inline_html(b['text'])}</p>")
        elif b["type"] == "callout":
            parts.append(f'<div class="callout">{inline_html(b["text"])}</div>')
        elif b["type"] == "metrics":
            cards = "".join(
                f'<div class="metric"><div class="metric-value">{inline_html(m["value"])}</div>'
                f'<div class="metric-label">{inline_html(m["label"])}</div></div>'
                for m in b["items"])
            parts.append(f'<div class="metrics">{cards}</div>')
        elif b["type"] == "list":
            tag = "ol" if b["ordered"] else "ul"
            items = "".join(f"<li>{inline_html(it)}</li>" for it in b["items"])
            parts.append(f"<{tag}>{items}</{tag}>")
        elif b["type"] == "table":
            head = "".join(f"<th>{inline_html(h)}</th>" for h in b["headers"])
            body = "".join(
                "<tr>" + "".join(f"<td>{inline_html(c)}</td>" for c in row) + "</tr>"
                for row in b["rows"])
            parts.append(f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead>'
                         f"<tbody>{body}</tbody></table></div>")
    body = "\n".join(parts)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{ size: Letter; margin: 0.75in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "{p['font']}", "Segoe UI", Arial, sans-serif; color: {p['ink']};
       background: {p['bg']}; margin: 0 auto; max-width: 7.5in; line-height: 1.45;
       font-size: 11pt; text-wrap: pretty; }}
h1 {{ color: {p['accent']}; font-size: 22pt; margin: 0 0 4pt; }}
h2 {{ color: {p['accent']}; font-size: 15pt; margin: 18pt 0 6pt;
      border-bottom: 2px solid {p['accent']}; padding-bottom: 3pt; }}
h3 {{ font-size: 12pt; margin: 12pt 0 4pt; }}
code {{ font-family: "{p['mono']}", Consolas, monospace; font-size: 10pt;
        background: {p['callout_bg']}; padding: 0 3px; border-radius: 3px; }}
a {{ color: {p['accent']}; }}
.callout {{ background: {p['callout_bg']}; border-left: 4px solid {p['accent']};
            padding: 8pt 10pt; margin: 8pt 0; break-inside: avoid; }}
.metrics {{ display: flex; gap: 10pt; margin: 10pt 0; break-inside: avoid; }}
.metric {{ flex: 1; border: 1px solid {p['accent']}; border-radius: 6pt;
           padding: 8pt; text-align: center; }}
.metric-value {{ font-size: 16pt; font-weight: 700; color: {p['accent']}; }}
.metric-label {{ font-size: 9pt; text-transform: uppercase; letter-spacing: 0.06em; }}
.tablewrap {{ break-inside: avoid; margin: 8pt 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 10pt; }}
th {{ background: {p['table_header_bg']}; color: {p['table_header_ink']};
      text-align: left; padding: 5pt 7pt; }}
td {{ padding: 4pt 7pt; border-bottom: 1px solid #ddd; }}
tr:nth-child(even) td {{ background: {p['row_alt_bg']}; }}
tr {{ break-inside: avoid; }}
</style></head><body>
{body}
</body></html>
"""


# --------------------------- deck renderer ---------------------------------

def slide_plan(blocks: list[dict]) -> list[dict]:
    """Split blocks into slides: '#' is the title slide, each '##' starts a slide,
    and an overflowing body continues onto '(cont.)' slides instead of clipping."""
    slides: list[dict] = []
    title = subtitle = ""
    current: dict | None = None

    def close():
        nonlocal current
        if current is not None:
            slides.append(current)
            current = None

    for b in blocks:
        if b["type"] == "heading" and b["level"] == 1 and not title:
            title = b["text"]
            continue
        if b["type"] == "heading" and b["level"] == 2:
            close()
            current = {"title": b["text"], "blocks": []}
            continue
        if current is None:
            if b["type"] == "para" and not subtitle:
                subtitle = b["text"]
                continue
            current = {"title": title or "Report", "blocks": []}
        current["blocks"].append(b)
    close()

    # Continuation: count body lines per slide; split lists across slides.
    final: list[dict] = []
    for s in slides:
        budget = DECK_BODY_LINES
        cur = {"title": s["title"], "blocks": []}
        for b in s["blocks"]:
            cost = {"para": 2, "callout": 2, "metrics": 3,
                    "table": 1 + len(b.get("rows", [])),
                    "heading": 1}.get(b["type"], 0)
            if b["type"] == "list":
                cost = len(b["items"])
                while cost > budget and budget < DECK_BODY_LINES:
                    final.append(cur)
                    cur = {"title": s["title"] + " (cont.)", "blocks": []}
                    budget = DECK_BODY_LINES
                if cost > budget:  # list longer than a whole slide: split it
                    head, tail = b["items"][:budget], b["items"][budget:]
                    cur["blocks"].append({**b, "items": head})
                    while tail:
                        final.append(cur)
                        cur = {"title": s["title"] + " (cont.)", "blocks": []}
                        chunk, tail = tail[:DECK_BODY_LINES], tail[DECK_BODY_LINES:]
                        cur["blocks"].append({**b, "items": chunk})
                        budget = DECK_BODY_LINES - len(chunk)
                    continue
            elif cost > budget and cur["blocks"]:
                final.append(cur)
                cur = {"title": s["title"] + " (cont.)", "blocks": []}
                budget = DECK_BODY_LINES
            cur["blocks"].append(b)
            budget -= min(cost, DECK_BODY_LINES)
        final.append(cur)
    return [{"kind": "title", "title": title or "Report", "subtitle": subtitle}] + \
           [{"kind": "content", **s} for s in final]


def render_pptx(blocks: list[dict], palette: dict, out: Path) -> None:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
    except ImportError:
        raise SystemExit("report-render: error: the deck path needs python-pptx "
                         "(pip install python-pptx); the HTML path needs nothing")

    def color(hexstr: str) -> "RGBColor":
        return RGBColor.from_string(hexstr.lstrip("#"))

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    for s in slide_plan(blocks):
        slide = prs.slides.add_slide(blank)
        if s["kind"] == "title":
            tb = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(11.7), Inches(1.5))
            para = tb.text_frame.paragraphs[0]
            run = para.add_run(); run.text = s["title"]
            run.font.size = Pt(44); run.font.bold = True
            run.font.color.rgb = color(palette["accent"])
            if s.get("subtitle"):
                sub = tb.text_frame.add_paragraph()
                r2 = sub.add_run(); r2.text = s["subtitle"]
                r2.font.size = Pt(18); r2.font.color.rgb = color(palette["ink"])
            continue

        head = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9))
        hr = head.text_frame.paragraphs[0].add_run(); hr.text = s["title"]
        hr.font.size = Pt(28); hr.font.bold = True
        hr.font.color.rgb = color(palette["accent"])

        y = 1.4
        for b in s["blocks"]:
            if b["type"] == "metrics":
                n = len(b["items"]); width = min(3.6, 12.0 / max(n, 1))
                for j, m in enumerate(b["items"]):
                    box = slide.shapes.add_textbox(Inches(0.6 + j * (width + 0.2)),
                                                   Inches(y), Inches(width), Inches(1.1))
                    vf = box.text_frame; vf.word_wrap = True
                    v = vf.paragraphs[0].add_run(); v.text = strip_inline(m["value"])
                    v.font.size = Pt(26); v.font.bold = True
                    v.font.color.rgb = color(palette["accent"])
                    lp = vf.add_paragraph(); l = lp.add_run(); l.text = strip_inline(m["label"])
                    l.font.size = Pt(11); l.font.color.rgb = color(palette["ink"])
                y += 1.4
            elif b["type"] == "table":
                rows, cols = len(b["rows"]) + 1, len(b["headers"])
                height = 0.32 * rows
                shape = slide.shapes.add_table(rows, cols, Inches(0.6), Inches(y),
                                               Inches(12.1), Inches(height))
                tbl = shape.table
                for c, htext in enumerate(b["headers"]):
                    cell = tbl.cell(0, c); cell.text = strip_inline(htext)
                    cell.fill.solid(); cell.fill.fore_color.rgb = color(palette["table_header_bg"])
                    for pgh in cell.text_frame.paragraphs:
                        for run in pgh.runs:
                            run.font.color.rgb = color(palette["table_header_ink"])
                            run.font.size = Pt(12); run.font.bold = True
                for ri, row in enumerate(b["rows"], start=1):
                    for c, cell_text in enumerate(row[:cols]):
                        cell = tbl.cell(ri, c); cell.text = strip_inline(cell_text)
                        for pgh in cell.text_frame.paragraphs:
                            for run in pgh.runs:
                                run.font.size = Pt(11)
                y += height + 0.25
            else:
                box = slide.shapes.add_textbox(Inches(0.6), Inches(y), Inches(12.1), Inches(4.8))
                tf = box.text_frame; tf.word_wrap = True
                if b["type"] == "list":
                    used = 0
                    for k, item in enumerate(b["items"]):
                        pgh = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                        run = pgh.add_run(); run.text = ("• " if not b["ordered"] else f"{k+1}. ") + strip_inline(item)
                        run.font.size = Pt(16); run.font.color.rgb = color(palette["ink"])
                        used += 1
                    y += 0.32 * used + 0.15
                elif b["type"] == "callout":
                    run = tf.paragraphs[0].add_run(); run.text = strip_inline(b["text"])
                    run.font.size = Pt(15); run.font.italic = True
                    run.font.color.rgb = color(palette["accent"])
                    y += 0.7
                elif b["type"] == "heading":
                    run = tf.paragraphs[0].add_run(); run.text = strip_inline(b["text"])
                    run.font.size = Pt(18); run.font.bold = True
                    run.font.color.rgb = color(palette["ink"])
                    y += 0.5
                else:  # para
                    run = tf.paragraphs[0].add_run(); run.text = strip_inline(b["text"])
                    run.font.size = Pt(15); run.font.color.rgb = color(palette["ink"])
                    y += 0.6
    prs.save(str(out))


# --------------------------- entry point ------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--palette", type=Path, default=PALETTE_PATH)
    args = ap.parse_args()

    palette = json.loads(args.palette.read_text(encoding="utf-8"))
    blocks = parse(args.src.read_text(encoding="utf-8-sig"))
    title = next((b["text"] for b in blocks if b["type"] == "heading" and b["level"] == 1),
                 args.src.stem)

    suffix = args.out.suffix.lower()
    if suffix == ".html":
        args.out.write_text(render_html(blocks, palette, title), encoding="utf-8")
    elif suffix == ".pptx":
        render_pptx(blocks, palette, args.out)
    else:
        raise SystemExit(f"report-render: error: unsupported output {suffix!r}; use .html or .pptx")
    print(f"report-render: {args.out}")


if __name__ == "__main__":
    main()
