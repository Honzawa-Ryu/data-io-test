import pytest

pytest.importorskip("matplotlib")

from iobench.results.report import aggregate
from iobench.results.schema import Condition, Metrics, ProbeResult, TrialRecord
from iobench.results.writer import to_rows


def _record(fmt, storage, size, tput, tid):
    return TrialRecord(
        trial_id=tid,
        timestamp="2026-07-22T10:00:00+09:00",
        probe=ProbeResult(hostname="h", node_class="X", cpu_cores=8, ram_gb=64.0, gpu_present=False),
        condition=Condition(
            format=fmt, storage_logical=storage, shard_or_chunk_size_bytes=size,
            num_workers=8, shuffle_mode="shard", decode=True,
        ),
        metrics=Metrics(throughput_samples_s=tput, throughput_mb_s=tput * 9),
        cache_state="cold", repetition_index=0, repetition_total=1,
        library_version="abc", purpose="campaign", subcommand="loader",
    )


def test_generate_plots(tmp_path):
    from iobench.results.plots import generate_all_plots

    records = []
    i = 0
    for storage in ["nfs", "ssd_scratch"]:
        for size in [100 * 1024**2, 500 * 1024**2, 1024**3]:
            records.append(_record("webdataset", storage, size, 300 + size / 1e7, f"t{i}"))
            i += 1
    agg = aggregate(to_rows(records))
    generated = generate_all_plots(agg, str(tmp_path))
    names = {p.split("/")[-1] for p in generated}
    # スループット比較とシャードサイズ掃引の両方が生成される
    assert "throughput_comparison.png" in names
    assert "shardsize_sweep.png" in names


def test_degradation_and_breakeven_outputs(tmp_path):
    from iobench.results.plots import generate_all_plots

    agg = aggregate(to_rows([_record("raw", "nfs", None, 500.0, "t0")]))
    degradation_rows = [{"condition_key": ("raw", "nfs"), "degradation_ratio": 0.6}]
    breakeven_rows = [{"format": "raw", "breakeven_epochs": 5}]
    generated = generate_all_plots(agg, str(tmp_path), degradation_rows=degradation_rows, breakeven_rows=breakeven_rows)
    names = {p.split("/")[-1] for p in generated}
    assert "degradation.png" in names
    assert "breakeven_table.csv" in names
