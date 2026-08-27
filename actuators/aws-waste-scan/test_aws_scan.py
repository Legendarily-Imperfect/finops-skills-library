"""aws-waste-scan tests: read-only is enforced, findings come from state not billing."""

from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from aws_scan import assert_read_only, commands, scan, ReadOnlyViolation

TODAY = date(2026, 6, 30)


def runner_with(payloads: dict):
    executed = []

    def run(cmd):
        assert_read_only(cmd)
        executed.append(cmd)
        key = cmd[2].replace("describe-", "")  # volumes/addresses/instances/snapshots
        return {
            "volumes": {"Volumes": payloads.get("Volumes", [])},
            "addresses": {"Addresses": payloads.get("Addresses", [])},
            "instances": {"Reservations": payloads.get("Reservations", [])},
            "snapshots": {"Snapshots": payloads.get("Snapshots", [])},
        }[key]
    run.executed = executed
    return run


def test_mutating_command_refused():
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["aws", "ec2", "delete-volume", "--volume-id", "vol-1"])
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(["aws", "s3", "describe-something"])


def test_all_emitted_commands_are_reads():
    for cmd in commands("us-east-1").values():
        assert_read_only(cmd)  # must not raise


def test_unattached_volume_found():
    run = runner_with({"Volumes": [{"VolumeId": "vol-orphan", "State": "available",
                                    "Size": 100, "CreateTime": "2025-01-01T00:00:00+00:00"}]})
    report = scan(run, "us-east-1", TODAY, 365)
    assert report["summary"] == {"unattached_volume": 1}
    assert report["findings"][0]["id"] == "vol-orphan"
    assert "delete-volume" in report["findings"][0]["remediation_hint"]


def test_associated_eip_skipped_unassociated_found():
    run = runner_with({"Addresses": [
        {"AllocationId": "eipalloc-used", "PublicIp": "1.1.1.1", "AssociationId": "assoc-1"},
        {"AllocationId": "eipalloc-idle", "PublicIp": "2.2.2.2"},
    ]})
    report = scan(run, "", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["eipalloc-idle"]


def test_stopped_instance_carries_its_volumes_as_evidence():
    run = runner_with({"Reservations": [{"Instances": [{
        "InstanceId": "i-stopped", "InstanceType": "m5.large",
        "BlockDeviceMappings": [{"Ebs": {"VolumeId": "vol-a"}}, {"Ebs": {"VolumeId": "vol-b"}}],
    }]}]})
    report = scan(run, "", TODAY, 365)
    f = report["findings"][0]
    assert f["class"] == "stopped_instance"
    assert f["evidence"]["attached_volumes"] == ["vol-a", "vol-b"]


def test_snapshot_age_threshold_is_the_line():
    run = runner_with({"Snapshots": [
        {"SnapshotId": "snap-old", "StartTime": "2025-06-29T12:00:00+00:00", "VolumeId": "vol-x"},
        {"SnapshotId": "snap-young", "StartTime": "2025-07-02T12:00:00+00:00", "VolumeId": "vol-y"},
    ]})
    report = scan(run, "", TODAY, 365)
    assert [f["id"] for f in report["findings"]] == ["snap-old"]
    assert report["findings"][0]["evidence"]["age_days"] == 366


def test_scan_never_executes_a_remediation_hint():
    run = runner_with({"Volumes": [{"VolumeId": "vol-1", "Size": 8}]})
    scan(run, "", TODAY, 365)
    for cmd in run.executed:
        assert cmd[2].startswith("describe-")
