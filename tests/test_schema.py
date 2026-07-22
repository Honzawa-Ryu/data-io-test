from iobench.results.schema import Condition, Metrics, MountInfo, ProbeResult, TrialRecord


def _sample_probe() -> ProbeResult:
    return ProbeResult(
        hostname="node01",
        node_class="X",
        cpu_cores=8,
        ram_gb=64.0,
        gpu_present=False,
        mounts=[MountInfo(path="/mnt/nfs", fs_type="nfs4")],
    )


def test_trial_record_round_trip():
    record = TrialRecord(
        trial_id="t1",
        timestamp="2026-07-22T10:00:00+09:00",
        probe=_sample_probe(),
        condition=Condition(
            format="raw", storage_logical="nfs", num_workers=4, shuffle_mode="none", decode=True
        ),
        metrics=Metrics(throughput_samples_s=100.0),
        cache_state="cold",
        repetition_index=0,
        repetition_total=3,
        library_version="abc123",
        purpose="dev",
        subcommand="loader",
    )
    dumped = record.model_dump_json()
    restored = TrialRecord.model_validate_json(dumped)
    assert restored.trial_id == "t1"
    assert restored.probe.node_class == "X"


def test_invalid_node_class_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProbeResult(
            hostname="node01",
            node_class="W",  # X/Y/Z以外は不正
            cpu_cores=8,
            ram_gb=64.0,
            gpu_present=False,
        )
