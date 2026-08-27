#!/usr/bin/env python3
"""Helpers for parity tests: locate a peer repo, load its config, name the drift.

A parity test reads the OTHER system's real config and fails when your copy
drifts. These helpers carry the three mechanics: env-overridable location
(absent peer -> None -> skip, never fail, never silently pass), allowlisted
diffs so every failure line is actionable, and diffs that name the drift
precisely enough to act on without opening either file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def locate(env_var: str, default_path: str) -> Path | None:
    """The peer repo's path, or None when absent (callers skip, with a reason)."""
    root = Path(os.environ.get(env_var, default_path))
    return root if root.exists() else None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def diff(ours: dict, theirs: dict, allowlist: list[str] | None = None) -> list[str]:
    """Named, actionable differences, minus the allowlist.

    Keys compare flat; nested dicts recurse with dotted paths. An allowlisted
    path silences that key and everything under it: the allowlist is where a
    KNOWN divergence lives, beside a comment saying why it is accepted.
    """
    allow = set(allowlist or [])
    problems: list[str] = []

    def allowed(path: str) -> bool:
        return any(path == a or path.startswith(a + ".") for a in allow)

    def walk(a: dict, b: dict, prefix: str) -> None:
        for key in sorted(set(a) | set(b)):
            path = f"{prefix}{key}"
            if allowed(path):
                continue
            if key not in b:
                problems.append(f"only in ours: {path} = {a[key]!r}")
            elif key not in a:
                problems.append(f"only in theirs: {path} = {b[key]!r}")
            elif isinstance(a[key], dict) and isinstance(b[key], dict):
                walk(a[key], b[key], path + ".")
            elif a[key] != b[key]:
                problems.append(f"value differs at {path}: ours {a[key]!r}, theirs {b[key]!r}")

    walk(ours, theirs, "")
    return problems
