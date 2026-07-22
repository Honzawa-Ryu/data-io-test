import pytest

from iobench.results.schema import Condition, Metrics, MountInfo, ProbeResult, TrialRecord
from iobench.results.writer import (
    MixedCacheStateError,
    append_record,
    check_cache_state_consistency,
    load_records,
    to_rows,
)


def _record(cache_state: str, trial_id: str) -> TrialRecord:
    return TrialRecord(
        trial_id=trial_id,
        timestamp="2026-07-22T10:00:00+09:00",
        probe=ProbeResult(
            hostname="node01",
            node_class="X",
            cpu_cores=8,
            ram_gb=64.0,
            gpu_present=False,
            mounts=[MountInfo(path="/mnt/nfs", fs_type="nfs4")],
        ),
        condition=Condition(
            format="raw", storage_logical="nfs", num_workers=4, shuffle_mode="none", decode=True
        ),
        metrics=Metrics(throughput_samples_s=100.0),
        cache_state=cache_state,
        repetition_index=0,
        repetition_total=3,
        library_version="abc123",
        purpose="dev",
        subcommand="loader",
    )


def test_append_and_load_round_trip(tmp_path):
    jsonl_path = tmp_path / "trials.jsonl"
    append_record(_record("cold", "t1"), str(jsonl_path))
    append_record(_record("cold", "t2"), str(jsonl_path))

    records = load_records(str(jsonl_path))
    assert [r.trial_id for r in records] == ["t1", "t2"]


def test_mixed_cache_state_raises():
    records = [_record("cold", "t1"), _record("warm", "t2")]
    with pytest.raises(MixedCacheStateError):
        check_cache_state_consistency(records)


def test_consistent_cache_state_ok():
    records = [_record("cold", "t1"), _record("cold", "t2")]
    check_cache_state_consistency(records)  # 例外が出ないこと


def test_to_rows_flattens_metrics():
    rows = to_rows([_record("cold", "t1")])
    assert rows[0]["throughput_samples_s"] == 100.0
    assert rows[0]["node_class"] == "X"
