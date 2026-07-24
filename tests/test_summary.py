import pandas as pd

from test_report_breakeven import _loader_record, _probe, _staging_record

from iobench.results.schema import StorageTrialRecord
from iobench.results.summary import (
    loader_table,
    render_summary_md,
    staging_table,
    storage_table,
)
from iobench.results.writer import append_record, load_storage_records


def _storage_record(trial_id: str, target_logical: str = "ssd_scratch") -> StorageTrialRecord:
    return StorageTrialRecord(
        trial_id=trial_id,
        timestamp="2026-07-24T10:00:00+09:00",
        probe=_probe(),
        target="/scratch/honzawa",
        target_logical=target_logical,
        preset="seq_1m_qd32_nj8",
        runtime_sec=10,
        metrics={"throughput_mb_s": 2100.5, "iops": 2100.0},
        library_version="abc123",
    )


def test_staging_table_columns_and_values():
    df = staging_table([_staging_record("s1", t_stage=100.0)])
    assert list(df["format"]) == ["raw"]
    assert df.loc[0, "tool"] == "rsync"
    assert df.loc[0, "t_stage_s"] == 100.0
    assert df.loc[0, "size_gb"] == 3.0


def test_loader_table_aggregates_median_and_count():
    records = [
        _loader_record("l1", "hdd", epoch_seconds=40.0),
        _loader_record("l2", "hdd", epoch_seconds=50.0),
        _loader_record("l3", "hdd", epoch_seconds=60.0),
    ]
    df = loader_table(records)
    assert len(df) == 1
    assert df.loc[0, "epoch_s_median"] == 50.0
    assert df.loc[0, "n"] == 3


def test_storage_table_flattens_metrics():
    df = storage_table([_storage_record("st1")])
    assert df.loc[0, "target"] == "ssd_scratch"
    assert df.loc[0, "throughput_mb_s"] == 2100.5


def test_storage_record_jsonl_round_trip(tmp_path):
    path = tmp_path / "trials_storage.jsonl"
    append_record(_storage_record("st1"), str(path))
    loaded = load_storage_records(str(path))
    assert len(loaded) == 1
    assert loaded[0].preset == "seq_1m_qd32_nj8"
    assert loaded[0].metrics["iops"] == 2100.0


def test_render_summary_md_all_sections():
    md = render_summary_md(
        node_label="andre01",
        storage_df=storage_table([_storage_record("st1")]),
        staging_df=staging_table([_staging_record("s1", t_stage=100.0)]),
        loader_df=loader_table(
            [
                _loader_record("l1", "hdd", 50.0, cache_state="cold"),
                _loader_record("l2", "hdd", 45.0, cache_state="warm"),
            ]
        ),
        breakeven_df=pd.DataFrame([{"format": "raw", "breakeven_epochs": 1}]),
    )
    for section in ["ストレージ素性", "ステージング転送", "cold", "warm", "損益分岐"]:
        assert section in md
    assert "seq_1m_qd32_nj8" in md
    assert "rsync" in md


def test_render_summary_md_storage_missing_hint():
    md = render_summary_md(
        node_label="andre01",
        storage_df=pd.DataFrame(),
        staging_df=pd.DataFrame(),
        loader_df=pd.DataFrame(),
        breakeven_df=pd.DataFrame(),
    )
    assert "未計測" in md
