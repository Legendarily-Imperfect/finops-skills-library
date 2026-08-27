"""The drift test teams skip and regret.

A schema without an implementation makes the model call a tool that does not
exist (a runtime error at best). An implementation without a schema is
unreachable code that reads like coverage. Set-equality catches both the day
the catalog changes, not the day a user finds out.
"""

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tools import TOOL_DEFINITIONS, TOOL_REGISTRY, execute_tool


def test_schemas_and_registry_are_the_same_set():
    schema_names = {d["name"] for d in TOOL_DEFINITIONS}
    registry_names = set(TOOL_REGISTRY)
    assert schema_names == registry_names, (
        f"only in schemas: {schema_names - registry_names}; "
        f"only in registry: {registry_names - schema_names}"
    )


def test_unknown_tool_returns_error_not_exception():
    result = json.loads(asyncio.run(execute_tool("no_such_tool", {})))
    assert result["success"] is False and "Unknown tool" in result["error"]


def test_bad_arguments_return_error_not_exception():
    result = json.loads(asyncio.run(execute_tool("get_spend", {"bogus_arg": 1})))
    assert result["success"] is False and "Invalid arguments" in result["error"]


def test_every_schema_description_states_the_summary_rule_or_passthrough():
    """Descriptions are model-facing contracts; the discipline belongs in them."""
    for d in TOOL_DEFINITIONS:
        text = d["description"].lower()
        assert ("summary" in text) or ("pass" in text), d["name"]
