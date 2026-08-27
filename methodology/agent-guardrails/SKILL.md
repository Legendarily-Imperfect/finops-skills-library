---
name: agent-guardrails
description: >-
  How to keep an LLM agent from inventing a number, with a vendor-agnostic reference
  implementation you can drop into any agent loop. Use when building or reviewing any
  agent over financial, clinical, legal, or compliance data; when someone says "the bot
  made up a figure", "how do we stop hallucinated numbers", "add guardrails", "validate
  the model's answer", "our chatbot quoted a budget that doesn't exist"; or before
  shipping anything where a confidently wrong number has consequences. The stack is three
  layers plus two disciplines, and the hard case is the third layer: fabricated figures
  sitting alongside SUCCESSFUL tool calls, where everything looks healthy and the number
  is wrong. The reference code is pure functions over strings: no model, no SDK, no
  network, testable in milliseconds, usable from any provider's loop.
---

# agent-guardrails

## The Stack

| Layer | Catches | Mechanism |
|---|---|---|
| 1. Prompt rules | the cheap majority | Absolute data-integrity rules in the system prompt: every figure traces to a tool result, uncertainty disclosed, no confidence bluffing |
| 2. Fabrication guard | figures with no data behind them | Post-response check: reply contains figures AND (no tools ran, or every tool failed) → replace the reply, never ship it |
| 3. Grounding guard | figures beside successful tools | Extract every dollar and percent from the reply; each must trace to a number some tool returned this turn. Untraceable figures go back for repair |

Plus two disciplines that make the layers cheap:

- **Pre-computed summaries.** Servers total; the model reads `summary.total`. A model that never does arithmetic cannot do it wrong, and layer 3 gets exact strings to trace.
- **Tool errors that instruct.** Every tool error embeds "STOP. Tell the user this source is unavailable. Do NOT fabricate." The instruction rides in-band, where the model is already looking.

## Repair, Not Withhold

When layer 3 fires, do not discard the answer: the failing figures are known precisely and the draft is usually one wrong number away from correct. Send them back as a user turn offering exactly two remedies: call the tool that returns the right figure, or rewrite using only figures already in hand. Bound the rounds (one is usually enough); withhold only when rounds are exhausted.

**Quote figures in the form the model wrote them.** Telling a model `150000.0 is untraceable` when it wrote `$150,000.00` sends it hunting for a string that is not there. The reference implementation carries `(kind, raw, value)` for exactly this.

## What Counts As Grounded

- A figure a **tool returned this turn**: grounded.
- A figure the **user supplied**: grounded (pass user numbers in; quoting someone back is not fabrication).
- A **percentage derivable from figures already in the reply** (a/b within rounding): grounded, so a correctly computed delta passes.
- Everything else: ungrounded, including "obviously right" arithmetic the model did itself. That is what pre-computed summaries are for.

## Reference Implementation

`guards.py`: `extract_figures`, `numbers_in`, `ungrounded_figures`, `fabrication_verdict`, `build_correction_prompt`. Pure stdlib, no imports beyond `re`/`decimal`. Wire it after your loop's final response, before yielding to the user; on a hit, append the correction prompt and continue the loop.

```powershell
python -m pytest -q
```

## Non-Goals

Prompt-injection defense, jailbreak resistance, and factual claims that are not figures. This stack makes numbers traceable; it does not make prose true.
