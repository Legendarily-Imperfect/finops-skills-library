---
name: azure-waste-scan
description: >-
  Read-only scan of live Azure state for waste the cost export cannot see. Use when
  someone says "what's orphaned in Azure", "find unattached disks", "scan for waste",
  "unused public IPs", "are any VMs stopped but billing". The Azure-specific trap this
  skill exists for: "Stopped" is not "Deallocated". A VM stopped from inside the OS
  still bills compute at the full rate; only deallocation stops the meter, and the cost
  export shows the charge either way without telling you which state caused it. Five
  finding classes, all az list reads: stopped-but-not-deallocated VMs (the expensive
  mistake), deallocated VMs (disks still billing), unattached managed disks, orphaned
  public IPs, old snapshots. Read-only is enforced in code: the runner refuses any az
  command whose verb chain does not end in list, and remediation commands are printed
  as hints for a human, never executed.
---

# azure-waste-scan

## Data Contract

**In:** optional `--resource-group` (default: whole subscription), `--snapshot-age-days` (default 365), `--today` for reproducible runs. **Out:** JSON: findings (class, id, evidence, a remediation hint that is never run) and a per-class summary. No dollars: pair the ids with your billing data (`waste-classify`) for the money.

## Rules

- **Stopped and deallocated are different classes** because they are different problems: one is still paying for compute, the other only for disks. The stopped finding says so in its evidence, in capitals, because this is the most expensive state confusion in Azure.
- **Read-only is a code path, not a promise.** The guard walks the verb chain (tokens before the first flag) and refuses anything not ending in `list`; a test asserts every command the scan issued was a read.
- **Remediation hints ride along, unexecuted.** Deallocate/delete commands are printed for a human who has reviewed the finding.

## Usage

```powershell
python azure_scan.py --emit-cli
python azure_scan.py --resource-group my-rg --snapshot-age-days 365 --out azure-waste.json
python -m pytest -q
```

## Prerequisites Beyond The Baseline

Live mode needs the `az` CLI logged in with Reader on the scope. `--emit-cli` needs nothing.

## Non-Goals

Cost math (pair findings with billing data), rightsizing (`rightsize-on-peaks`), storage accounts/app services/other resource types (v1 is compute-and-disk scope), and any write.
