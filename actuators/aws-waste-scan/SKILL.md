---
name: aws-waste-scan
description: >-
  Read-only scan of live AWS account state for waste the billing export cannot see. Use
  when someone says "what's orphaned in our AWS account", "find unattached volumes",
  "scan for waste", "unused elastic IPs", "old snapshots". The gap this skill fills: a
  billed EBS volume looks identical in the CUR whether attached or orphaned; only the
  account API knows status=available. Four checks, all ec2 describe-* reads: unattached
  volumes, unassociated Elastic IPs (billed precisely BECAUSE they are idle), stopped
  instances (compute is free but their EBS and EIPs keep billing), and self-owned
  snapshots past an age threshold. Read-only is enforced in code, not promised in prose:
  the runner refuses any command that is not an ec2 describe-* read, and remediation
  commands are printed as hints for a human, never executed.
---

# aws-waste-scan

## Data Contract

**In:** `--region`, `--snapshot-age-days` (default 365), `--today` for reproducible runs. **Out:** JSON: findings (class, id, evidence, a remediation hint that is never run) and a per-class summary. No dollars: pair the ids with your billing data (`waste-classify`) for the money.

## Rules

- **Read-only is a code path, not a promise.** `assert_read_only` refuses anything that is not `aws ec2 describe-*` before it executes, and a test asserts every command the scan issued was a read.
- **Remediation hints ride along, unexecuted.** Each finding prints the delete/release/terminate command a human would run after review. The tool never runs them.
- **Stopped is not free.** A stopped instance's finding lists its attached volumes because those, not the halted compute, are the bill.
- **One region per invocation.** Loop regions in your shell; a silent multi-region merge hides where things live.

## Usage

```powershell
python aws_scan.py --region us-east-1 --emit-cli
python aws_scan.py --region us-east-1 --snapshot-age-days 365 --out aws-waste.json
python -m pytest -q
```

## Prerequisites Beyond The Baseline

Live mode needs the `aws` CLI authenticated with `ec2:Describe*` read permissions. `--emit-cli` needs nothing.

## Non-Goals

Cost math (pair findings with billing data), rightsizing running workloads (`rightsize-on-peaks`), S3/RDS/other services (v1 is EC2-scope, where most orphaned state lives), and any write.
