# FinOps Skills Library

Atomic, cloud-agnostic-where-it-counts FinOps tooling, written to be read by your AI agent as much as run by you. Every skill states its data contract (FOCUS columns in and out), its assumptions, its non-goals, and the reasoning behind each rule, so an agent can understand it and adapt it to your environment.

**Working name. Not yet published.** See `CATALOG.md` for the full tool list, layers, and build order.

## Layers

| Layer | What Lives Here |
|---|---|
| `collectors/` | Cloud-specific pulls: AWS CUR, Azure Cost Management, GCP billing export, vendor platforms, OTEL token telemetry |
| `normalizers/` | FOCUS normalization, conformance checking, tag reconciliation |
| `analyzers/` | Showback, variance, forecast, anomalies, commitments, waste, AI spend, spend-change drivers, exec briefs |
| `assurance/` | Invoice tie-out, sync verification, parity checks |
| `actuators/` | Cloud-specific waste scans and rightsizing, read-only by design |
| `output/` | Report rendering to PDF and deck |
| `methodology/` | Agent guardrails and read-only tool design, no cloud required |
| `enforcement/` | Pooled LLM spend caps (work in progress; the only tool here that writes) |
| `synthetic-data/` | FOCUS-shaped demo data so nothing here needs your real billing |

## Rules Of The Repo

- Analysis is cloud-agnostic; collection and actuation are cloud-specific. The FOCUS boundary is load-bearing.
- Every figure a tool emits is badged billing or estimated.
- Actuators never write. The one writing tool lives in `enforcement/` and says so loudly.
- No client code, names, or figures, ever. Illustrative data only.

License: Apache-2.0. See LICENSE and NOTICE.

## Prerequisites

The global list is deliberately short; each tool states its own extras in its SKILL.md, and a tool never assumes more than this baseline.

| Program | Version | Needed For |
|---|---|---|
| Python | 3.11+ (3.12 recommended) | Every scripted tool; standard library only unless a tool says otherwise |
| pytest | any current | Running a tool's tests (`python -m pytest -q`) |
| Git | any current | Cloning and updating |

Per-tool extras you may meet later: cloud CLIs or SDK auth for collectors (AWS, Azure, GCP), `python-pptx` for deck rendering. Each is named in the tool that needs it, with install commands.

