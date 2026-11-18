# Catalog

Every tool in this library, grouped by layer in build order. Each tool is a folder holding a `SKILL.md` (the data contract, rules, and non-goals) and, where it has one, a Python script and its tests. Only tools that exist in this repository are listed.

Run any tool's tests from its folder with `python -m pytest -q`.

## Counts

| Layer | Tools |
|---|---|
| `collectors/` | 5 |
| `normalizers/` | 3 |
| `analyzers/` | 10 |
| `assurance/` | 3 |
| `actuators/` | 4 |
| `output/` | 1 |
| `methodology/` | 2 |
| `enforcement/` | 1 |
| **Total** | **29** |

`ai-spend` is a written method with no script and no tests. `finops-tool-design` ships a reference registry (`reference/tools.py`) with a parity test rather than a command-line tool.

`synthetic-data/` holds demo billing data and is not a tool; see its README.

## Collectors (5)

Cloud-specific pulls: AWS CUR, Azure Cost Management, GCP billing export, vendor platforms, OTEL token telemetry.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `aws-cur-pull` | `collectors/aws-cur-pull/` | Pull a CUR 2.0 billing period from S3 and concatenate its parts safely. | bucket, prefix, export name, billing period | one CSV, parts joined under one header | Yes, 6 tests (`test_aws_pull.py`) |
| `azure-cost-pull` | `collectors/azure-cost-pull/` | Pull the latest Azure Cost Management export run for a period. | storage account, container, export path, period | one CSV, latest export run only | Yes, 6 tests (`test_azure_pull.py`) |
| `gcp-billing-pull` | `collectors/gcp-billing-pull/` | Pull the GCP BigQuery billing export with correct partition discipline. | project, dataset, table, day window | flattened billing CSV; `--emit-sql` prints the query only | Yes, 9 tests (`test_gcp_pull.py`) |
| `otel-token-pull` | `collectors/otel-token-pull/` | Pull per-user LLM token usage from a Prometheus-compatible store, correctly. | metric name, time window, optional user | CSV of tokens per user, model, and bucket; `--emit-promql` prints the query | Yes, 6 tests (`test_otel_pull.py`) |
| `vendor-pull` | `collectors/vendor-pull/` | Cardinality-partitioned vendor API puller: months, then sub-dimension, never offset. | vendor-config.json, date range | CSV of vendor rows plus a pull manifest | Yes, 6 tests (`test_vendor_pull.py`) |

## Normalizers (3)

FOCUS normalization, conformance checking, and tag reconciliation.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `focus-conform` | `normalizers/focus-conform/` | Validate a CSV against the FOCUS core column contract; name every violation. | any CSV | violation report; exit 0, 1, or 2 | Yes, 10 tests (`test_conform.py`) |
| `focus-normalize` | `normalizers/focus-normalize/` | Normalize a provider billing export into FOCUS columns. | provider billing CSV, mapping | FOCUS core CSV; unmapped columns kept as `x_src_*` | Yes, 8 tests (`test_normalize.py`) |
| `tag-reconcile` | `normalizers/tag-reconcile/` | Canonicalize owner tags against one map; report every defect with its dollars. | FOCUS CSV, owner-map.json | defect report JSON; optional CSV with `x_owner_canonical` | Yes, 6 tests (`test_reconcile.py`) |

## Analyzers (10)

Showback, variance, forecast, anomalies, commitments, waste, AI spend, spend-change drivers, and exec briefs.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `ai-spend` | `analyzers/ai-spend/` | Size, attribute, and govern an organization's AI and LLM spend as its own domain instead of a line buried in compute. | none (methodology, no script) | written method, no output | No |
| `anomaly-detect` | `analyzers/anomaly-detect/` | Per-series spend anomaly detection: each series against its own baseline. | FOCUS CSV, grouping dimension | JSON hits ranked by excess dollars | Yes, 6 tests (`test_detect.py`) |
| `budget-variance` | `analyzers/budget-variance/` | Actual vs budget by owner, ranked by variance dollars, with fatal file validation. | FOCUS CSV, budgets.json | JSON per-owner variance, ranked by dollars | Yes, 8 tests (`test_variance.py`) |
| `commitment-coverage` | `analyzers/commitment-coverage/` | Commitment coverage and utilization, reported together, unused commitments named. | FOCUS CSV | JSON coverage and utilization, unused commitments named | Yes, 5 tests (`test_coverage.py`) |
| `exec-brief` | `analyzers/exec-brief/` | Assemble a leadership memo from analyzer outputs; copy numbers, never recompute. | analyzer JSON files | markdown memo for report-render | Yes, 5 tests (`test_brief.py`) |
| `explain-spend-change` | `analyzers/explain-spend-change/` | Decompose a spend change into ranked drivers along the dimension that explains it. | FOCUS CSV, two time windows | JSON ranked drivers and residual | Yes, 6 tests (`test_explain.py`) |
| `forecast` | `analyzers/forecast/` | Period-end projection from actuals: run-rate and linear trend, both shown. | FOCUS CSV, target period | JSON run-rate and linear projections, badged estimated | Yes, 6 tests (`test_forecast.py`) |
| `showback` | `analyzers/showback/` | Per-owner spend allocation with the untagged remainder as its own named line. | FOCUS CSV | JSON per-owner spend with an untagged line | Yes, 5 tests (`test_showback.py`) |
| `unit-economics` | `analyzers/unit-economics/` | Cost per business unit-of-output, with the denominator's provenance printed. | FOCUS CSV, units file | JSON cost per unit, units source echoed | Yes, 6 tests (`test_unitcost.py`) |
| `waste-classify` | `analyzers/waste-classify/` | Classify waste from FOCUS signals; billed and recoverable are different numbers. | FOCUS CSV, optional config | JSON billed and recoverable dollars by class | Yes, 6 tests (`test_classify.py`) |

## Assurance (3)

Invoice tie-out, sync verification, and parity checks.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `parity-check` | `assurance/parity-check/` | Helpers for parity tests: locate a peer repo, load its config, name the drift. | your config, a peer repo's config | named diff of drift | Yes, 6 tests (`test_parity.py`) |
| `spend-tieout` | `assurance/spend-tieout/` | Three-leg spend reconciliation that names gap causes instead of printing a difference. | FOCUS CSV, source total, optional app total | JSON tie or gap verdicts with quantified causes | Yes, 7 tests (`test_tieout.py`) |
| `sync-check` | `assurance/sync-check/` | Verify a sync log: stale, skipped-clear, and closed-period writes all block. | sync log, patterns.json | PASS or BLOCK per rule; exit 0, 2, or 3 | Yes, 8 tests (`test_check_sync.py`) |

## Actuators (4)

Cloud-specific waste scans and rightsizing, read-only by design.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `aws-waste-scan` | `actuators/aws-waste-scan/` | Read-only AWS waste scan: account state the billing export cannot see. | region, snapshot age | JSON findings and summary, no dollars | Yes, 7 tests (`test_aws_scan.py`) |
| `azure-waste-scan` | `actuators/azure-waste-scan/` | Read-only Azure waste scan: account state the cost export cannot see. | resource group, snapshot age | JSON findings and summary, no dollars | Yes, 7 tests (`test_azure_scan.py`) |
| `gcp-waste-scan` | `actuators/gcp-waste-scan/` | Read-only GCP waste scan: project state the billing export cannot see. | project, snapshot age | JSON findings and summary, no dollars | Yes, 7 tests (`test_gcp_scan.py`) |
| `rightsize-on-peaks` | `actuators/rightsize-on-peaks/` | Distribution statistics and peak-based sizing for utilization series. | utilization series, current capacity | peak-based capacity, badged estimated, stats inline | Yes, 8 tests (`test_usage_stats.py`) |

## Output (1)

Report rendering to print-ready HTML and deck.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `report-render` | `output/report-render/` | Render report markdown to print-ready Letter HTML or a 16:9 deck. | markdown file | print-ready Letter HTML or 16:9 .pptx | Yes, 11 tests (`test_render.py`) |

## Methodology (2)

Agent guardrails and read-only tool design, no cloud required.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `agent-guardrails` | `methodology/agent-guardrails/` | Vendor-agnostic numeric guardrails for LLM agents over financial data. | model reply text, tool-result numbers | ungrounded figures, verdict, correction prompt | Yes, 12 tests (`test_guards.py`) |
| `finops-tool-design` | `methodology/finops-tool-design/` | Reference tool surface: schemas, registry, one dispatcher. Copy and grow. | none (pattern) | reference tool registry and parity test | Yes, 4 tests (`reference/test_registry_parity.py`) |

## Enforcement (1)

Pooled LLM spend caps. The only tool in the library that writes, and it writes only its own local ledger.

| Tool | Path | What It Does | Inputs | Outputs | Tests |
|---|---|---|---|---|---|
| `llm-spend-caps` | `enforcement/llm-spend-caps/` | Pooled LLM spend-cap enforcer: check before the call, record after it. | caps-config.json, local JSONL ledger | allow or deny verdict (exit 0 or 3), ledger entries, status | Yes, 10 tests (`test_caps.py`) |
