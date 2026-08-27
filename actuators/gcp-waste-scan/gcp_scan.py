#!/usr/bin/env python3
"""Read-only GCP waste scan: project state the billing export cannot see.

The GCP-specific inversion: a reserved static external IP bills MORE when
it is NOT in use. Idle is the charged state, so the waste signal is
status=RESERVED, the opposite of the intuition that attached things cost.
Four checks, all gcloud list reads: unattached persistent disks (no users),
reserved-but-unused external addresses, TERMINATED instances (compute
free, their disks still billing), and old snapshots.

Read-only is enforced, not promised: the runner refuses any gcloud command
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
        print(f"gcp-waste-scan: refusing non-read command: {' '.join(cmd)}",
              file=sys.stderr, flush=True)
        super().__init__(2)


def assert_read_only(cmd: list[str]) -> None:
    """Every executed command is a `gcloud ... list` read. Anything else refuses."""
    verbs = []
    for tok in cmd[1:]:
        if tok.startswith("-"):
            break  # flags (and their values) are not verbs
        verbs.append(tok)
    if not cmd or cmd[0] != "gcloud" or not verbs or verbs[-1] != "list":
        raise ReadOnlyViolation(cmd)


def default_runner(cmd: list[str]) -> list:
    assert_read_only(cmd)
    proc = subprocess.run(cmd + ["--format=json"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"gcp-waste-scan: `{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def commands(project: str) -> dict[str, list[str]]:
    proj = ["--project", project]
    return {
        "disks": ["gcloud", "compute", "disks", "list"] + proj,
        "addresses": ["gcloud", "compute", "addresses", "list"] + proj,
        "instances": ["gcloud", "compute", "instances", "list"] + proj,
        "snapshots": ["gcloud", "compute", "snapshots", "list"] + proj,
    }


def _age_days(iso_ts: str, today: date) -> int:
    return (today - date.fromisoformat(iso_ts[:10])).days


def scan(run, project: str, today: date, snapshot_age_days: int) -> dict:
    cmds = commands(project)
    for cmd in cmds.values():
        assert_read_only(cmd)
    findings: list[dict] = []

    for disk in run(cmds["disks"]):
        if disk.get("users"):
            continue
        findings.append({
            "class": "unattached_disk", "id": disk["name"],
            "evidence": {"size_gb": disk.get("sizeGb"), "type": disk.get("type", "").split("/")[-1],
                         "zone": disk.get("zone", "").split("/")[-1]},
            "remediation_hint": f"gcloud compute disks delete {disk['name']} "
                                f"--zone {disk.get('zone', '<zone>').split('/')[-1]} --project {project}",
        })

    for addr in run(cmds["addresses"]):
        if addr.get("status") != "RESERVED" or addr.get("addressType") == "INTERNAL":
            continue
        findings.append({
            "class": "reserved_unused_address", "id": addr["name"],
            "evidence": {"address": addr.get("address"), "status": "RESERVED",
                         "note": "an idle reserved external IP bills MORE than one in use; "
                                 "idle is the charged state"},
            "remediation_hint": f"gcloud compute addresses delete {addr['name']} "
                                f"--region {addr.get('region', '<region>').split('/')[-1]} --project {project}",
        })

    for inst in run(cmds["instances"]):
        if inst.get("status") != "TERMINATED":
            continue
        disks = [d.get("deviceName", d.get("source", "").split("/")[-1])
                 for d in inst.get("disks", [])]
        findings.append({
            "class": "terminated_instance", "id": inst["name"],
            "evidence": {"machine_type": inst.get("machineType", "").split("/")[-1],
                         "attached_disks": disks,
                         "note": "TERMINATED compute is free; its disks and any "
                                 "reserved IPs are not"},
            "remediation_hint": f"gcloud compute instances delete {inst['name']} "
                                f"--zone {inst.get('zone', '<zone>').split('/')[-1]} --project {project}",
        })

    for snap in run(cmds["snapshots"]):
        created = snap.get("creationTimestamp", today.isoformat())
        age = _age_days(created, today)
        if age < snapshot_age_days:
            continue
        findings.append({
            "class": "old_snapshot", "id": snap["name"],
            "evidence": {"age_days": age, "threshold_days": snapshot_age_days,
                         "source_disk": snap.get("sourceDisk", "").split("/")[-1]},
            "remediation_hint": f"gcloud compute snapshots delete {snap['name']} --project {project}",
        })

    summary: dict[str, int] = {}
    for f in findings:
        summary[f["class"]] = summary.get(f["class"], 0) + 1
    return {"tool": "gcp-waste-scan", "project": project,
            "read_only": True, "findings": findings, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only GCP waste scan")
    ap.add_argument("--project", required=True)
    ap.add_argument("--snapshot-age-days", type=int, default=365)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible runs")
    ap.add_argument("--emit-cli", action="store_true",
                    help="print the exact read commands and exit; needs no access")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.emit_cli:
        for name, cmd in commands(args.project).items():
            print(f"# {name}")
            print(" ".join(cmd) + " --format=json")
        return

    today = date.fromisoformat(args.today) if args.today else date.today()
    report = scan(default_runner, args.project, today, args.snapshot_age_days)
    text = json.dumps(report, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
