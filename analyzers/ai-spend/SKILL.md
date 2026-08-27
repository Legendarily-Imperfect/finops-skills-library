---
name: ai-spend
description: >-
  Size, attribute, and govern an organization's AI and LLM spend as its own domain instead
  of a line buried in compute. Use when someone asks "what are we spending on AI", "who is
  using the tokens", "is Copilot worth it", "should we switch models", "AI budget", "token
  costs by team", "our LLM bill doubled", or wants an AI spend review. This is methodology,
  not a script: the collectors (otel-token-pull, the cloud collectors) fetch the numbers,
  and this skill is the analysis discipline that keeps those numbers honest. It exists
  because AI spend has failure modes normal cloud analysis does not: delta-temporality
  metrics that overstate by an order of magnitude when queried like counters, model labels
  with four spellings for one model, cache mechanics that make subsets meaningless, and
  per-user costs that are blended approximations presented as exact.
---

# ai-spend

## The Three Ledgers

AI spend hides in three places that never arrive in one export. Size all three or the total is fiction:

1. **Cloud AI services**: managed model endpoints and AI platforms inside the cloud bill (their service categories in FOCUS data).
2. **Direct API vendors**: model providers billed by invoice or marketplace, often outside the cloud bill entirely.
3. **Seats**: per-user AI subscriptions (coding assistants, chat products) living in SaaS or expense systems.

## Attribution Rules

- **Attribute people, then teams.** Token telemetry attributes to a person; people map to owners through the same canonical map `tag-reconcile` governs. Never build a second mapping.
- **Headline the total token flow, not the subsets.** Cache state moves tokens between input, output, and cache buckets without much changing their sum, so the subsets measure cache behavior and the sum measures the user. Measured across whole days, the sum is several times more stable than any subset.
- **Per-user dollar figures are blended approximations.** Rates vary by dimensions the telemetry does not record (region, context band). A per-user cost reconciles in total and is approximate per person; heavy long-context users are subsidized by everyone else. Say so in the report before someone treats it as payroll-grade.

## The Traps

- **Delta temporality.** Token metrics are per-interval deltas even when named like counters. Sum over time windows; rate-style functions overstate totals by an order of magnitude and the result still looks plausible.
- **Model label variants.** The same model appears under multiple label spellings (versioned, dated, aliased, bare). Normalize into a model family in one view and keep the raw label beside it, or one model scatters across rows and, once prices attach, across prices.
- **Partial-day reads.** The current day is incomplete in every ledger; a window ending today reads as a decline.
- **List versus contract rates.** Discounts vary by model, region, and token type. One blended discount ratio applied everywhere is wrong in both directions at once; use effective rates from the bill (cost over tokens) per model where possible.
- **Zero reads.** A zero in usage telemetry can mean "no usage" or "reading unavailable." Treat zero-spend rows for known-active users as suspect, not as savings.

## The Governance Frame

The prize is rarely "use less AI"; it is tier rebalancing (right model for the job), cache hygiene, and named ownership of the three ledgers. Frame findings as: total flow, its trend, its owners, the top rebalancing opportunities with estimated (badged) savings, and the one governance gap that most distorts attribution.

## Pairs With

`otel-token-pull` for the telemetry, `tag-reconcile` for ownership, `anomaly-detect` for spikes, `exec-brief` for the writeup, and the Groundwork kit's `llm-spend-caps` when governance needs enforcement rather than a memo.
