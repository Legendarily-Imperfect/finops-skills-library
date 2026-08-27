---
name: parity-check
description: >-
  A test pattern that reads another system's real config and fails when your copy of it
  drifts. Use when two codebases share a mapping, threshold, taxonomy, or constant list:
  "keep our copy in sync with the app", "how do we know this still matches production",
  "our numbers diverged from the dashboard", "the fork went stale", or any time
  documentation restates something a repo already owns. The history that earned this
  pattern: the same three legacy names resolved to three different owners depending on
  which of four hand-restated canonicalizers read them, and nothing failed. A parity test
  turns shared constants from documentation that quietly goes stale into documentation
  that fails a test when it does. Three mechanics make it work: skip when the other repo
  is absent so bare machines still run the suite, an allowlist for known accepted
  divergences so failures stay signal, and the discipline that ZERO SKIPS IS THE ONLY
  GREEN THAT COUNTS, because a skipped parity test and a passing one look identical in
  the output.
---

# parity-check

## Data Contract

**In:** your copy (a dict, usually loaded from your JSON/config) and theirs (located via an environment variable with a default path, loaded from their repo). **Out:** a named diff: keys only in yours, keys only in theirs, values that disagree, each minus the allowlist.

## The Three Mechanics

1. **`locate()` with env override.** `PEER_REPO` (or your name for it) overrides a default path. Absent repo returns `None`, and the test skips with a reason naming the variable, so the suite still runs on a machine that has only your repo.
2. **`diff()` with an allowlist.** Known accepted divergences live in your config next to the data they excuse. Every line a parity failure prints must be actionable, or the failure gets ignored and the pattern dies.
3. **Zero skips is the only green that counts.** In the environment where both repos exist (CI, your machine), run with skips surfaced: `python -m pytest -rs` and treat any `SKIPPED .*parity` line as a failure of the run, not of the code. A green suite with a skipped parity test has verified nothing about parity.

## Usage

```python
from parity import locate, load_json, diff

PEER = locate("FINOPS_APP_CONFIG", "c:/path/to/app/backend/config")

@pytest.mark.skipif(PEER is None, reason="peer repo absent; set FINOPS_APP_CONFIG")
def test_owner_map_matches_app():
    theirs = load_json(PEER / "owners.json")
    problems = diff(MY_MAP, theirs, allowlist=MY_MAP.get("parity_allowlist", []))
    assert not problems, "\n".join(problems)
```

```powershell
python -m pytest -q          # runs everywhere
python -m pytest -rs         # where both repos exist: any parity SKIP is a red flag
```

## Non-Goals

Syncing anything. A parity failure is a decision point for a human: adopt theirs, push yours upstream, or allowlist the divergence with a comment saying why. Auto-sync is how a wrong value propagates with a green check beside it.
