"""gcp-waste-scan tests: idle is the charged state for reserved IPs, reads only."""

from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from gcp_scan import assert_read_only, commands, scan, ReadOnlyViolation

TODAY = date(2026, 6, 30)


def runner_with(payloads: dict):
    executed = []

    def run(cmd):
        assert_read_only(cmd)
        executed.append(cmd)
        return payloads.get(cmd[2], [])  # disks/addresses/instances/snapshots
    run.executed = executed
    return run


def test_mutating_command_refused():
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["gcloud", "compute", "disks", "delete", "d1"])
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["gcloud", "compute", "instances", "stop", "i1"])


def test_all_emitted_commands_are_reads():
    for cmd in commands("my-proj").values():
        assert_read_only(cmd)


def test_disk_with_users_skipped_unattached_found():
    run = runner_with({"disks": [
        {"name": "disk-used", "users": ["projects/p/zones/z/instances/vm1"], "sizeGb": "100"},
        {"name": "disk-orphan", "users": [], "sizeGb": "500",
         "type": "projects/p/zones/z/diskTypes/pd-ssd", "zone": "projects/p/zones/us-central1-a"},
    ]})
    report = scan(run, "my-proj", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["disk-orphan"]
    assert report["findings"][0]["evidence"]["zone"] == "us-central1-a"


def test_reserved_external_ip_found_in_use_and_internal_skipped():
    run = runner_with({"addresses": [
        {"name": "ip-in-use", "status": "IN_USE", "addressType": "EXTERNAL"},
        {"name": "ip-idle", "status": "RESERVED", "addressType": "EXTERNAL",
         "address": "34.1.2.3", "region": "projects/p/regions/us-central1"},
        {"name": "ip-internal", "status": "RESERVED", "addressType": "INTERNAL"},
    ]})
    report = scan(run, "my-proj", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["ip-idle"]
    assert "bills MORE" in report["findings"][0]["evidence"]["note"]


def test_terminated_instance_carries_its_disks_as_evidence():
    run = runner_with({"instances": [
        {"name": "vm-running", "status": "RUNNING"},
        {"name": "vm-dead", "status": "TERMINATED",
         "machineType": "zones/z/machineTypes/n2-standard-4",
         "zone": "projects/p/zones/us-east1-b",
         "disks": [{"deviceName": "boot"}, {"deviceName": "data-1"}]},
    ]})
    report = scan(run, "my-proj", TODAY, 365)
    f = report["findings"][0]
    assert f["class"] == "terminated_instance"
    assert f["evidence"]["attached_disks"] == ["boot", "data-1"]


def test_snapshot_age_threshold_is_the_line():
    run = runner_with({"snapshots": [
        {"name": "snap-old", "creationTimestamp": "2025-06-29T04:00:00.000-07:00",
         "sourceDisk": "projects/p/zones/z/disks/d"},
        {"name": "snap-young", "creationTimestamp": "2026-06-01T04:00:00.000-07:00"},
    ]})
    report = scan(run, "my-proj", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["snap-old"]


def test_scan_never_executes_a_remediation_hint():
    run = runner_with({"disks": [{"name": "d", "users": []}]})
    scan(run, "my-proj", TODAY, 365)
    for cmd in run.executed:
        verbs = []
        for tok in cmd[1:]:
            if tok.startswith("-"):
                break
            verbs.append(tok)
        assert verbs[-1] == "list"
