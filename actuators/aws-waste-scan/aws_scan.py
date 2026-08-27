#!/usr/bin/env python3
"""Read-only AWS waste scan: account state the billing export cannot see.

A billed volume looks identical in the CUR whether attached or orphaned;
only the account API knows status=available. Four checks, all reads:
unattached EBS volumes, unassociated Elastic IPs, stopped instances
(whose EBS volumes and EIPs keep billing), and old self-owned snapshots.

Read-only is enforced, not promised: every command must be an ec2
describe-* read or the runner refuses before executing anything.
Remediation commands are PRINTED as hints for a human, never run.

The runner is injectable: run(cmd: list[str]) -> parsed JSON. The default
runner shells out to the aws CLI; tests inject fakes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date


class ReadOnlyViolation(SystemExit):
    def __init__(self, cmd: list[str]):
        print(f"aws-waste-scan: refusing non-read command: {' '.join(cmd)}",
              file=sys.stderr, flush=True)
        super().__init__(2)


def assert_read_only(cmd: list[str]) -> None:
    """Every executed command is `aws ec2 describe-*`. Anything else refuses."""
    if len(cmd) < 3 or cmd[0] != "aws" or cmd[1] != "ec2" or not cmd[2].startswith("describe-"):
        raise ReadOnlyViolation(cmd)


def default_runner(cmd: list[str]) -> dict:
    assert_read_only(cmd)
    proc = subprocess.run(cmd + ["--output", "json"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"aws-waste-scan: `{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def commands(region: str) -> dict[str, list[str]]:
    base = ["aws", "ec2"]
    reg = ["--region", region] if region else []
    return {
        "volumes": base + ["describe-volumes", "--filters", "Name=status,Values=available"] + reg,
        "addresses": base + ["describe-addresses"] + reg,
        "instances": base + ["describe-instances",
                             "--filters", "Name=instance-state-name,Values=stopped"] + reg,
        "snapshots": base + ["describe-snapshots", "--owner-ids", "self"] + reg,
    }


def _age_days(iso_ts: str, today: date) -> int:
    return (today - date.fromisoformat(iso_ts[:10])).days


def scan(run, region: str, today: date, snapshot_age_days: int) -> dict:
    cmds = commands(region)
    for cmd in cmds.values():
        assert_read_only(cmd)
    findings: list[dict] = []

    for vol in run(cmds["volumes"]).get("Volumes", []):
        findings.append({
            "class": "unattached_volume", "id": vol["VolumeId"],
            "evidence": {"status": vol.get("State", "available"),
                         "size_gb": vol.get("Size"),
                         "created": vol.get("CreateTime", "")[:10]},
            "remediation_hint": f"aws ec2 delete-volume --volume-id {vol['VolumeId']}",
        })

    for addr in run(cmds["addresses"]).get("Addresses", []):
        if addr.get("AssociationId"):
            continue
        findings.append({
            "class": "unassociated_eip", "id": addr.get("AllocationId", addr.get("PublicIp", "")),
            "evidence": {"public_ip": addr.get("PublicIp")},
            "remediation_hint": f"aws ec2 release-address --allocation-id {addr.get('AllocationId', '')}",
        })

    for resv in run(cmds["instances"]).get("Reservations", []):
        for inst in resv.get("Instances", []):
            vols = [bdm["Ebs"]["VolumeId"] for bdm in inst.get("BlockDeviceMappings", [])
                    if "Ebs" in bdm]
            findings.append({
                "class": "stopped_instance", "id": inst["InstanceId"],
                "evidence": {"type": inst.get("InstanceType"),
                             "attached_volumes": vols,
                             "note": "stopped compute is free; its EBS and EIPs are not"},
                "remediation_hint": f"aws ec2 terminate-instances --instance-ids {inst['InstanceId']}",
            })

    for snap in run(cmds["snapshots"]).get("Snapshots", []):
        age = _age_days(snap.get("StartTime", today.isoformat()), today)
        if age < snapshot_age_days:
            continue
        findings.append({
            "class": "old_snapshot", "id": snap["SnapshotId"],
            "evidence": {"age_days": age, "volume_id": snap.get("VolumeId"),
                         "threshold_days": snapshot_age_days},
            "remediation_hint": f"aws ec2 delete-snapshot --snapshot-id {snap['SnapshotId']}",
        })

    summary: dict[str, int] = {}
    for f in findings:
        summary[f["class"]] = summary.get(f["class"], 0) + 1
    return {"tool": "aws-waste-scan", "region": region or "(default profile region)",
            "read_only": True, "findings": findings, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only AWS waste scan")
    ap.add_argument("--region", default="")
    ap.add_argument("--snapshot-age-days", type=int, default=365)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible runs")
    ap.add_argument("--emit-cli", action="store_true",
                    help="print the exact read commands and exit; needs no access")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.emit_cli:
        for name, cmd in commands(args.region).items():
            print(f"# {name}")
            print(" ".join(cmd) + " --output json")
        return

    today = date.fromisoformat(args.today) if args.today else date.today()
    report = scan(default_runner, args.region, today, args.snapshot_age_days)
    text = json.dumps(report, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
