from iobench.multi import compute_degradation
from iobench.results.schema import Condition, Metrics, ProbeResult, TrialRecord


def _record(tput: float, trial_id: str) -> TrialRecord:
    return TrialRecord(
        trial_id=trial_id,
        timestamp="2026-07-22T10:00:00+09:00",
        probe=ProbeResult(hostname="h", node_class="X", cpu_cores=8, ram_gb=64.0, gpu_present=False),
        condition=Condition(
            format="webdataset", storage_logical="nfs", num_workers=8, shuffle_mode="shard", decode=True
        ),
        metrics=Metrics(throughput_samples_s=tput),
        cache_state="cold",
        repetition_index=0,
        repetition_total=1,
        library_version="abc",
        purpose="dev",
        subcommand="loader",
    )


def test_degradation_ratio():
    baseline = [_record(1000.0, "b1")]
    multi = [_record(600.0, "m1"), _record(500.0, "m2")]  # 平均550
    results = compute_degradation(baseline, multi)
    assert len(results) == 1
    assert results[0].concurrency == 2
    assert abs(results[0].degradation_ratio - 0.55) < 1e-6


def test_no_matching_condition_skipped():
    baseline = [_record(1000.0, "b1")]
    # 条件が異なるmultiは突合されない
    m = _record(600.0, "m1")
    m.condition.storage_logical = "ssd_scratch"
    results = compute_degradation(baseline, [m])
    assert results == []
