"""azure-waste-scan tests: stopped is not deallocated, and reads are the only verbs."""

from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from azure_scan import assert_read_only, commands, scan, ReadOnlyViolation

TODAY = date(2026, 6, 30)


def runner_with(payloads: dict):
    executed = []

    def run(cmd):
        assert_read_only(cmd)
        executed.append(cmd)
        verbs = []
        for tok in cmd[1:]:
            if tok.startswith("-"):
                break
            verbs.append(tok)
        key = {"disk": "disks", "public-ip": "public_ips",
               "vm": "vms", "snapshot": "snapshots"}[verbs[-2]]
        return payloads.get(key, [])
    run.executed = executed
    return run


def test_mutating_command_refused():
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["az", "vm", "deallocate", "--name", "x"])
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["az", "disk", "delete", "--name", "x"])


def test_all_emitted_commands_are_reads():
    for cmd in commands("my-rg").values():
        assert_read_only(cmd)


def test_stopped_and_deallocated_are_different_classes():
    run = runner_with({"vms": [
        {"name": "vm-stopped", "powerState": "VM stopped",
         "hardwareProfile": {"vmSize": "Standard_D4s_v5"}, "resourceGroup": "rg"},
        {"name": "vm-dealloc", "powerState": "VM deallocated", "resourceGroup": "rg"},
        {"name": "vm-running", "powerState": "VM running", "resourceGroup": "rg"},
    ]})
    report = scan(run, "rg", TODAY, 365)
    by_class = {f["class"]: f for f in report["findings"]}
    assert set(by_class) == {"stopped_not_deallocated", "deallocated_vm"}
    assert "STILL BILLING COMPUTE" in by_class["stopped_not_deallocated"]["evidence"]["note"]
    assert "deallocate" in by_class["stopped_not_deallocated"]["remediation_hint"]


def test_attached_disk_skipped_unattached_found():
    run = runner_with({"disks": [
        {"name": "disk-used", "diskState": "Attached", "diskSizeGB": 128},
        {"name": "disk-orphan", "diskState": "Unattached", "diskSizeGB": 512,
         "sku": {"name": "Premium_LRS"}, "resourceGroup": "rg"},
    ]})
    report = scan(run, "rg", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["disk-orphan"]
    assert report["findings"][0]["evidence"]["size_gb"] == 512


def test_orphaned_public_ip_found():
    run = runner_with({"public_ips": [
        {"name": "ip-used", "ipConfiguration": {"id": "/nic/1"}},
        {"name": "ip-idle", "ipAddress": "20.1.2.3", "sku": {"name": "Standard"},
         "resourceGroup": "rg"},
    ]})
    report = scan(run, "rg", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["ip-idle"]


def test_snapshot_age_threshold_is_the_line():
    run = runner_with({"snapshots": [
        {"name": "snap-old", "timeCreated": "2025-06-29T08:00:00+00:00", "resourceGroup": "rg"},
        {"name": "snap-young", "timeCreated": "2026-01-01T08:00:00+00:00", "resourceGroup": "rg"},
    ]})
    report = scan(run, "rg", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["snap-old"]


def test_scan_never_executes_a_remediation_hint():
    run = runner_with({"disks": [{"name": "d", "diskState": "Unattached"}]})
    scan(run, "", TODAY, 365)
    for cmd in run.executed:
        verbs = []
        for tok in cmd[1:]:
            if tok.startswith("-"):
                break
            verbs.append(tok)
        assert verbs[-1] == "list"
