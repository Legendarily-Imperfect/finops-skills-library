#!/usr/bin/env python3
"""Reference tool surface: schemas, registry, one dispatcher. Copy and grow.

The shape matters more than the contents: schemas as data, implementations in
a dict, a dispatcher that returns errors with instructions instead of raising,
and a parity test (beside this file) asserting the two sets never drift.
"""

from __future__ import annotations

import json

# Schemas: what the model sees. Data, not code, so they can be linted and diffed.
TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_spend",
        "description": "Total spend for an owner and window. Returns records AND a "
                       "server-computed summary; read summary.total, never sum records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
        },
    },
    {
        "name": "get_budget_variance",
        "description": "Actual vs budget by owner, ranked by overspend. Pass-through of "
                       "the system of record's numbers; this tool computes nothing.",
        "input_schema": {"type": "object", "properties": {"owner": {"type": "string"}}},
    },
]


async def get_spend(owner: str | None = None,
                    start_date: str | None = None,
                    end_date: str | None = None) -> str:
    # Real implementations call the system of record and RETURN ITS summary.
    payload = {"records": [], "summary": {"total": "0", "count": 0},
               "note": "reference stub; wire to your system of record"}
    return json.dumps(payload)


async def get_budget_variance(owner: str | None = None) -> str:
    payload = {"by_owner": [], "summary": {"total_variance": "0"},
               "note": "reference stub; pass the app's numbers through unchanged"}
    return json.dumps(payload)


# Registry: what actually runs. The parity test keeps this and TOOL_DEFINITIONS equal.
TOOL_REGISTRY = {
    "get_spend": get_spend,
    "get_budget_variance": get_budget_variance,
}


async def execute_tool(name: str, arguments: dict) -> str:
    """Errors return instructions in-band; the model is already looking there."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return json.dumps({"success": False, "error": f"Unknown tool: {name}"})
    try:
        return await fn(**arguments)
    except TypeError as e:
        return json.dumps({"success": False, "error": f"Invalid arguments: {e}"})
    except Exception as e:  # noqa: BLE001 - the boundary must not raise into the loop
        return json.dumps({
            "success": False,
            "error": f"Tool failed: {e}",
            "instruction": "STOP. Tell the user this data source is unavailable. "
                           "Do NOT fabricate numbers.",
        })
