"""agent-guardrails tests: the hard case is figures beside successful tools."""

from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from guards import (extract_figures, numbers_in, ungrounded_figures,
                    fabrication_verdict, build_correction_prompt)

TOOL_OUT = ['{"summary": {"actual_total": 150000.00, "budget_total": 200000.00}}']


def test_extract_keeps_raw_form():
    figs = extract_figures("Spend was $150,000.00, up 12.5% vs plan")
    assert ("dollar", "$150,000.00", Decimal("150000.00")) in figs
    assert ("percent", "12.5%", Decimal("12.5")) in figs


def test_scale_suffixes():
    figs = extract_figures("about $1.2M this month")
    assert figs[0][2] == Decimal("1200000.0")


def test_grounded_reply_passes():
    reply = "Actual spend is $150,000.00 against a budget of $200,000.00."
    assert ungrounded_figures(reply, TOOL_OUT) == []


def test_fabricated_figure_beside_successful_tools_is_caught():
    """The founding case: green tools, wrong number."""
    reply = "Actual spend is $163,450.00 against a budget of $200,000.00."
    bad = ungrounded_figures(reply, TOOL_OUT)
    assert bad == [("dollar", "$163,450.00")]


def test_user_supplied_number_is_grounded():
    reply = "You asked about the $5,000.00 threshold; spend is $150,000.00."
    assert ungrounded_figures(reply, TOOL_OUT, extra_numbers=(Decimal("5000"),)) == []
    assert ungrounded_figures(reply, TOOL_OUT) == [("dollar", "$5,000.00")]


def test_derived_percent_passes():
    """150000/200000 = 75%: a correctly computed share must survive."""
    reply = "Spend of $150,000.00 is 75.0% of the $200,000.00 budget."
    assert ungrounded_figures(reply, TOOL_OUT) == []


def test_invented_percent_is_caught():
    reply = "Spend of $150,000.00 is 61.8% of the $200,000.00 budget."
    assert ("percent", "61.8%") in ungrounded_figures(reply, TOOL_OUT)


def test_rounding_to_cents_is_tolerated():
    reply = "Total: $150,000.00."
    assert ungrounded_figures(reply, ['{"total": 150000.004}']) == []


def test_correction_prompt_quotes_raw_form():
    prompt = build_correction_prompt([("dollar", "$163,450.00")])
    assert "$163,450.00" in prompt
    assert "163450.0" not in prompt
    assert "tool result" in prompt


def test_fabrication_verdicts():
    assert fabrication_verdict(3, 3, True, False) == "all_tools_failed"
    assert fabrication_verdict(0, 0, True, False) == "no_tools_ran"
    assert fabrication_verdict(3, 1, True, False) == "ok"      # partial failure: layer 3's job
    assert fabrication_verdict(0, 0, True, True) == "ok"       # greeting/refusal
    assert fabrication_verdict(0, 0, False, False) == "ok"     # no figures, nothing to guard


def test_numbers_in_reads_json_and_prose():
    pool = numbers_in(['{"a": 12.5}', "rows returned: 1,234"])
    assert Decimal("12.5") in pool and Decimal("1234") in pool


def test_word_after_dollar_is_not_a_scale_suffix():
    """"$200,000.00 budget" is not 200 billion dollars."""
    figs = extract_figures("the $200,000.00 budget and $3k more")
    assert figs[0][2] == Decimal("200000.00")
    assert figs[1][2] == Decimal("3000")
