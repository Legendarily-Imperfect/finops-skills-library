---
name: gcp-waste-scan
description: >-
  Read-only scan of live GCP project state for waste the billing export cannot see. Use
  when someone says "what's orphaned in GCP", "find unattached disks", "scan the project
  for waste", "unused static IPs", "terminated instances still costing money". The
  GCP-specific inversion this skill exists for: a reserved static external IP bills MORE
  when it is NOT in use; idle is the charged state, so the waste signal is
  status=RESERVED, the opposite of the intuition that attached things cost. Four checks,
  all gcloud list reads: unattached persistent disks (empty users), reserved-but-unused
  external addresses, TERMINATED instances (compute free, disks still billing), and old
  snapshots. Read-only is enforced in code: the runner refuses any gcloud command whose
  verb chain does not end in list, and remediation commands are printed as hints for a
  human, never executed.
---

# gcp-waste-scan

## Data Contract

**In:** `--project` (required), `--snapshot-age-days` (default 365), `--today` for reproducible runs. **Out:** JSON: findings (class, id, evidence, a remediation hint that is never run) and a per-class summary. No dollars: pair the ids with your billing data (`waste-classify`) for the money.

## Rules

- **RESERVED external addresses are findings; internal and in-use are not.** The pricing inversion is stated in the finding's evidence so the reader learns why an idle IP made a waste list.
- **Read-only is a code path, not a promise.** The guard walks the verb chain (tokens before the first flag) and refuses anything not ending in `list`; a test asserts every command the scan issued was a read.
- **Remediation hints ride along, unexecuted**, zone and project filled in from the resource so a human can run them after review.

## Usage

```powershell
python gcp_scan.py --project my-proj --emit-cli
python gcp_scan.py --project my-proj --snapshot-age-days 365 --out gcp-waste.json
python -m pytest -q
```

## Prerequisites Beyond The Baseline

Live mode needs the `gcloud` CLI authenticated with `compute.viewer` on the project. `--emit-cli` needs nothing.

## Non-Goals

Cost math (pair findings with billing data), rightsizing (`rightsize-on-peaks`), GKE/CloudSQL/other services (v1 is Compute Engine scope), and any write.
