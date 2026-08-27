#!/usr/bin/env python3
"""Vendor-agnostic numeric guardrails for LLM agents over financial data.

Pure functions over strings: no model, no SDK, no network. Wire them into any
provider's loop after the final response, before yielding to the user.

The hard case these exist for: fabricated figures sitting alongside SUCCESSFUL
tool calls. Green tools, confident prose, a plausible number that appears in no
tool result. The grounding guard extracts every dollar and percent from the
reply and requires each to trace to a number some tool returned this turn.

Figures travel as (kind, raw, value) so a correction prompt can quote the
figure in the form the model wrote it: telling a model `150000.0 is
untraceable` when it wrote `$150,000.00` sends it hunting for a string that
is not there.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Suffix must stand alone: "$200,000.00 budget" is not 200 billion dollars.
DOLLAR_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([KMBkmb])?(?![A-Za-z])")
PERCENT_RE = re.compile(r"(-?[\d,]+(?:\.\d+)?)\s*%")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
SCALE = {"K": Decimal("1e3"), "M": Decimal("1e6"), "B": Decimal("1e9")}
CENTS = Decimal("0.01")


def _dec(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def extract_figures(text: str) -> list[tuple[str, str, Decimal]]:
    """Every dollar and percent in the text as (kind, raw_as_written, value)."""
    out: list[tuple[str, str, Decimal]] = []
    for m in DOLLAR_RE.finditer(text):
        value = _dec(m.group(1))
        if value is None:
            continue
        if m.group(2):
            value *= SCALE[m.group(2).upper()]
        out.append(("dollar", m.group(0).strip(), value))
    for m in PERCENT_RE.finditer(text):
        value = _dec(m.group(1))
        if value is not None:
            out.append(("percent", m.group(0).strip(), value))
    return out


def numbers_in(texts: list[str]) -> set[Decimal]:
    """Every numeric token in the tool results, as Decimals."""
    found: set[Decimal] = set()
    for t in texts:
        for m in NUMBER_RE.finditer(t or ""):
            value = _dec(m.group(0))
            if value is not None:
                found.add(value)
    return found


def _matches(value: Decimal, pool: set[Decimal]) -> bool:
    """Exact, or equal at 2 decimal places: models legitimately round cents."""
    if value in pool:
        return True
    q = value.quantize(CENTS)
    return any(p.quantize(CENTS) == q for p in pool)


def ungrounded_figures(text: str,
                       tool_texts: list[str],
                       extra_numbers: tuple = ()) -> list[tuple[str, str]]:
    """Figures in the reply that trace to nothing a tool returned this turn.

    User-supplied numbers pass via extra_numbers: quoting someone back is not
    fabrication. A percent passes if it appears in the pool OR derives from two
    money figures already in the reply (a/b within rounding), so a correctly
    computed delta or share survives.
    """
    pool = numbers_in(tool_texts)
    for n in extra_numbers:
        d = n if isinstance(n, Decimal) else _dec(str(n))
        if d is not None:
            pool.add(d)

    figures = extract_figures(text)
    money_values = [v for k, _, v in figures if k == "dollar"]
    bad: list[tuple[str, str]] = []
    for kind, raw, value in figures:
        if _matches(value, pool):
            continue
        if kind == "percent" and _percent_derivable(value, money_values, pool):
            continue
        bad.append((kind, raw))
    return bad


def _percent_derivable(pct: Decimal, money: list[Decimal], pool: set[Decimal]) -> bool:
    candidates = list(pool) + money
    tol = Decimal("0.1")
    for a in candidates:
        for b in candidates:
            if b == 0:
                continue
            ratio = (a / b) * 100
            if abs(ratio - pct) <= tol or abs(abs(ratio - 100) - abs(pct)) <= tol:
                return True
    return False


def fabrication_verdict(tools_called: int, tools_failed: int,
                        has_figures: bool, is_non_data_reply: bool) -> str:
    """Layer 2: 'ok', 'all_tools_failed', or 'no_tools_ran'.

    Only fires when figures are present and the reply is not a greeting or
    refusal; those legitimately carry no data.
    """
    if not has_figures or is_non_data_reply:
        return "ok"
    if tools_called > 0 and tools_failed == tools_called:
        return "all_tools_failed"
    if tools_called == 0:
        return "no_tools_ran"
    return "ok"


def build_correction_prompt(bad: list[tuple[str, str]]) -> str:
    """Name the figures as written; offer exactly two remedies."""
    quoted = ", ".join(raw for _, raw in bad)
    return (
        f"Your draft contains figures that do not appear in any tool result from "
        f"this turn: {quoted}. Every figure must trace to a tool result. Do exactly "
        f"one of the following: (1) call the tool that returns the correct figure "
        f"and rewrite using its output, or (2) rewrite the answer using only figures "
        f"already present in this turn's tool results. Do not restate the "
        f"untraceable figures."
    )
