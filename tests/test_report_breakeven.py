from iobench.results.report import build_breakeven_rows
from iobench.results.schema import Condition, Metrics, ProbeResult, TrialRecord


def _probe() -> ProbeResult:
    return ProbeResult(
        hostname="andre01",
        node_class="andre01",
        cpu_cores=32,
        ram_gb=251.0,
        gpu_present=False,
    )


def _loader_record(trial_id: str, storage: str, epoch_seconds: float, cache_state: str = "warm") -> TrialRecord:
    return TrialRecord(
        trial_id=trial_id,
        timestamp="2026-07-24T10:00:00+09:00",
        probe=_probe(),
        condition=Condition(
            format="raw", storage_logical=storage, num_workers=8, shuffle_mode="shard", decode=True
        ),
        metrics=Metrics(throughput_samples_s=1000.0, epoch_seconds=epoch_seconds),
        cache_state=cache_state,
        repetition_index=0,
        repetition_total=1,
        library_version="abc123",
        purpose="dev",
        subcommand="loader",
    )


def _staging_record(
    trial_id: str, t_stage: float, fmt: str = "raw", cache_state: str = "cold"
) -> TrialRecord:
    return TrialRecord(
        trial_id=trial_id,
        timestamp="2026-07-24T10:00:00+09:00",
        probe=_probe(),
        condition=Condition(
            format=fmt,
            storage_logical="ssd_scratch",
            num_workers=0,
            shuffle_mode="none",
            decode=False,
            staging_tool="rsync",
            staging_src="hdd",
            staging_dst="ssd_scratch",
        ),
        metrics=Metrics(t_stage_seconds=t_stage, throughput_mb_s=326.0, staged_bytes=3_000_000_000),
        cache_state=cache_state,
        repetition_index=0,
        repetition_total=1,
        library_version="abc123",
        purpose="dev",
        subcommand="staging",
    )


def test_breakeven_rows_joins_staging_and_loader():
    records = [
        _staging_record("s1", t_stage=100.0),
        _loader_record("l1", "hdd", epoch_seconds=50.0, cache_state="cold"),
        _loader_record("l2", "ssd_scratch", epoch_seconds=30.0, cache_state="cold"),
    ]
    rows = build_breakeven_rows(records)
    assert len(rows) == 1
    row = rows[0]
    assert row["staging_tool"] == "rsync"
    assert row["cache_state"] == "cold"
    assert row["t_stage_seconds"] == 100.0
    assert row["t_epoch_direct_s"] == 50.0
    assert row["t_epoch_staged_s"] == 30.0
    assert row["breakeven_epochs"] == 5


def test_breakeven_rows_uses_median_over_repetitions():
    records = [
        _staging_record("s1", t_stage=90.0),
        _staging_record("s2", t_stage=100.0),
        _staging_record("s3", t_stage=110.0),
        _loader_record("l1", "hdd", epoch_seconds=40.0, cache_state="cold"),
        _loader_record("l2", "hdd", epoch_seconds=50.0, cache_state="cold"),
        _loader_record("l3", "hdd", epoch_seconds=60.0, cache_state="cold"),
        _loader_record("l4", "ssd_scratch", epoch_seconds=30.0, cache_state="cold"),
    ]
    rows = build_breakeven_rows(records)
    assert len(rows) == 1
    assert rows[0]["t_stage_seconds"] == 100.0
    assert rows[0]["t_epoch_direct_s"] == 50.0
    assert rows[0]["breakeven_epochs"] == 5


def test_breakeven_rows_no_join_across_cache_states():
    # cold staging と warm loader は突合しない(cache_state一致が必須)
    records = [
        _staging_record("s1", t_stage=100.0, cache_state="cold"),
        _loader_record("l1", "hdd", epoch_seconds=50.0, cache_state="warm"),
        _loader_record("l2", "ssd_scratch", epoch_seconds=30.0, cache_state="warm"),
    ]
    assert build_breakeven_rows(records) == []


def test_breakeven_rows_requires_both_storages():
    # dst側(ssd_scratch)のloader計測が無ければ行は作られない
    records = [
        _staging_record("s1", t_stage=100.0),
        _loader_record("l1", "hdd", epoch_seconds=50.0, cache_state="cold"),
    ]
    assert build_breakeven_rows(records) == []


def test_breakeven_rows_no_join_across_formats():
    records = [
        _staging_record("s1", t_stage=100.0, fmt="webdataset"),
        _loader_record("l1", "hdd", epoch_seconds=50.0, cache_state="cold"),
        _loader_record("l2", "ssd_scratch", epoch_seconds=30.0, cache_state="cold"),
    ]
    assert build_breakeven_rows(records) == []


def test_breakeven_rows_loader_only_or_empty():
    assert build_breakeven_rows([]) == []
    assert build_breakeven_rows([_loader_record("l1", "hdd", 50.0)]) == []
