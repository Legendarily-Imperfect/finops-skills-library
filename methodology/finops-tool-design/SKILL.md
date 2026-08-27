---
name: finops-tool-design
description: >-
  How to expose tools to an LLM agent over financial data without letting it change
  anything or compute a second version of the truth. Use when designing or reviewing an
  agent's tool surface: "what tools should the bot have", "should the agent be able to
  update records", "why does the chatbot's number differ from the dashboard", "design the
  tool registry", "the agent and the app disagree". The two ideas everything else follows
  from: bounded scope is the selling point, not a limitation to apologize for (an agent
  that refuses, has no data of its own, and cannot write is precisely why its numbers can
  be trusted); and one number per question (the agent reads the system of record's number,
  never computes a rival one, because two implementations of the same figure eventually
  disagree and nobody can say which is right). Ships a reference registry pattern with the
  parity test that keeps schemas and implementations from drifting apart.
---

# finops-tool-design

## The Rules

1. **Read-only by construction, not by policy.** Write endpoints are deliberately not exposed as tools. A state change happens in the owning system's UI, by a named person. "The model probably won't call it" is not a control.
2. **One number per question.** If the app computes a scorecard, the tool passes the app's cards through unchanged. An agent that grades locally with its own weights will disagree with the page, and the meeting spends its hour on which number is right instead of what to do.
3. **Pre-computed summaries.** Every list-returning tool also returns a server-side `summary` (totals, counts). The model reads `summary.actual_total`; it never sums records. This is also what makes grounding guards cheap (see `agent-guardrails`).
4. **Tool errors instruct.** The error payload embeds what the model should do: name the source as unavailable, do not fabricate. In-band beats system-prompt distance.
5. **Deterministic procedure loading.** Domain procedures load by keyword match in code, not by a tool the model chooses to call: a rule the model can forget to load is a rule that regresses the first time it forgets. Over-selection costs tokens; under-selection costs a wrong number, and those are not symmetric.
6. **Registry parity is a test, not a convention.** A schema without an implementation makes the model call a tool that does not exist; an implementation without a schema is unreachable. Assert set-equality in CI (see `reference/`).
7. **Subject assertion is explicit.** When a trusted front end names the human (a forwarded email header), the agent treats it as the caller's assertion and logs it, rather than pretending to verify what it cannot.
8. **Bounded scope, stated scope.** The agent says what it covers, refuses what it does not, and redirects adjacent questions to the owning tool. Refusal is a feature; every refusal is a hallucination that did not happen.

## Reference

`reference/tools.py` holds the minimal shape: schema list, registry dict, one dispatcher with error instructions. `reference/test_registry_parity.py` is the drift test. Copy both into your agent and grow them; the parity test is the part teams skip and regret.

```powershell
python -m pytest -q
```

## Pairs With

`agent-guardrails` for the response-side guards; the Groundwork kit for all of this wired into a working agent with the provider seam finished.
