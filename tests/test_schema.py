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


def test_node_class_is_free_form():
    # per-machineデプロイ方針によりクラス名は自由文字列(X/Y/Z限定は撤廃)
    probe = ProbeResult(
        hostname="node01",
        node_class="andre01",
        cpu_cores=8,
        ram_gb=64.0,
        gpu_present=False,
    )
    assert probe.node_class == "andre01"
