#!/usr/bin/env python3
"""Read-only Azure waste scan: account state the cost export cannot see.

The Azure-specific trap: "Stopped" is not "Deallocated". A VM stopped from
inside the OS (or via stop without deallocate) STILL BILLS COMPUTE at the
full rate; only deallocation stops the meter. The cost export shows the
charge either way and cannot tell you which state caused it. Four checks,
all az list reads: stopped-but-not-deallocated VMs (the expensive mistake),
deallocated VMs (compute free, disks still billing), unattached managed
disks, and orphaned public IPs, plus old snapshots.

Read-only is enforced, not promised: the runner refuses any az command
whose verb is not list. Remediation hints are printed, never executed.

The runner is injectable: run(cmd: list[str]) -> parsed JSON.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date


class ReadOnlyViolation(SystemExit):
    def __init__(self, cmd: list[str]):
        print(f"azure-waste-scan: refusing non-read command: {' '.join(cmd)}",
              file=sys.stderr, flush=True)
        super().__init__(2)


def assert_read_only(cmd: list[str]) -> None:
    """Every executed command is an `az ... list` read. Anything else refuses."""
    verbs = []
    for tok in cmd[1:]:
        if tok.startswith("-"):
            break  # flags (and their values) are not verbs
        verbs.append(tok)
    if not cmd or cmd[0] != "az" or not verbs or verbs[-1] != "list":
        raise ReadOnlyViolation(cmd)


def default_runner(cmd: list[str]) -> list:
    assert_read_only(cmd)
    proc = subprocess.run(cmd + ["-o", "json"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"azure-waste-scan: `{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def commands(resource_group: str) -> dict[str, list[str]]:
    rg = ["--resource-group", resource_group] if resource_group else []
    return {
        "disks": ["az", "disk", "list"] + rg,
        "public_ips": ["az", "network", "public-ip", "list"] + rg,
        "vms": ["az", "vm", "list", "-d"] + rg,
        "snapshots": ["az", "snapshot", "list"] + rg,
    }


def _age_days(iso_ts: str, today: date) -> int:
    return (today - date.fromisoformat(iso_ts[:10])).days


def scan(run, resource_group: str, today: date, snapshot_age_days: int) -> dict:
    cmds = commands(resource_group)
    for cmd in cmds.values():
        assert_read_only(cmd)
    findings: list[dict] = []

    for disk in run(cmds["disks"]):
        if disk.get("diskState") != "Unattached":
            continue
        findings.append({
            "class": "unattached_disk", "id": disk["name"],
            "evidence": {"disk_state": "Unattached", "size_gb": disk.get("diskSizeGB"),
                         "sku": (disk.get("sku") or {}).get("name")},
            "remediation_hint": f"az disk delete --name {disk['name']} "
                                f"--resource-group {disk.get('resourceGroup', '<rg>')} --yes",
        })

    for ip in run(cmds["public_ips"]):
        if ip.get("ipConfiguration"):
            continue
        findings.append({
            "class": "orphaned_public_ip", "id": ip["name"],
            "evidence": {"address": ip.get("ipAddress"),
                         "sku": (ip.get("sku") or {}).get("name")},
            "remediation_hint": f"az network public-ip delete --name {ip['name']} "
                                f"--resource-group {ip.get('resourceGroup', '<rg>')}",
        })

    for vm in run(cmds["vms"]):
        state = (vm.get("powerState") or "").lower()
        if state == "vm stopped":
            findings.append({
                "class": "stopped_not_deallocated", "id": vm["name"],
                "evidence": {"power_state": vm.get("powerState"),
                             "size": (vm.get("hardwareProfile") or {}).get("vmSize"),
                             "note": "STILL BILLING COMPUTE at the full rate; "
                                     "only deallocation stops the meter"},
                "remediation_hint": f"az vm deallocate --name {vm['name']} "
                                    f"--resource-group {vm.get('resourceGroup', '<rg>')}",
            })
        elif state == "vm deallocated":
            findings.append({
                "class": "deallocated_vm", "id": vm["name"],
                "evidence": {"power_state": vm.get("powerState"),
                             "note": "compute meter stopped; its disks keep billing"},
                "remediation_hint": f"az vm delete --name {vm['name']} "
                                    f"--resource-group {vm.get('resourceGroup', '<rg>')} --yes",
            })

    for snap in run(cmds["snapshots"]):
        created = snap.get("timeCreated", today.isoformat())
        age = _age_days(created, today)
        if age < snapshot_age_days:
            continue
        findings.append({
            "class": "old_snapshot", "id": snap["name"],
            "evidence": {"age_days": age, "threshold_days": snapshot_age_days},
            "remediation_hint": f"az snapshot delete --name {snap['name']} "
                                f"--resource-group {snap.get('resourceGroup', '<rg>')}",
        })

    summary: dict[str, int] = {}
    for f in findings:
        summary[f["class"]] = summary.get(f["class"], 0) + 1
    return {"tool": "azure-waste-scan",
            "scope": resource_group or "(whole subscription)",
            "read_only": True, "findings": findings, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only Azure waste scan")
    ap.add_argument("--resource-group", default="")
    ap.add_argument("--snapshot-age-days", type=int, default=365)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible runs")
    ap.add_argument("--emit-cli", action="store_true",
                    help="print the exact read commands and exit; needs no access")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.emit_cli:
        for name, cmd in commands(args.resource_group).items():
            print(f"# {name}")
            print(" ".join(cmd) + " -o json")
        return

    today = date.fromisoformat(args.today) if args.today else date.today()
    report = scan(default_runner, args.resource_group, today, args.snapshot_age_days)
    text = json.dumps(report, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
