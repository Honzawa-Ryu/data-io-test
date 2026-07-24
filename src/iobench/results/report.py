"""結果JSONLからの集計(中央値・min・max)と損益分岐表の構築。"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

import pandas as pd

from iobench.results.schema import TrialRecord

GROUP_KEYS = [
    "subcommand",
    "format",
    "storage_logical",
    "shard_or_chunk_size_bytes",
    "node_class",
    "num_workers",
    "shuffle_mode",
    "decode",
    "cache_state",
    "staging_tool",
    "staging_src",
    "staging_dst",
]

METRIC_KEYS = [
    "throughput_samples_s",
    "throughput_mb_s",
    "gpu_idle_ratio",
    "t_stage_seconds",
    "first_batch_latency_s",
    "degradation_ratio",
    "meta_ops_s",
    "epoch_seconds",
    "staged_bytes",
]


def aggregate(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    agg = df.groupby(GROUP_KEYS, dropna=False)[METRIC_KEYS].agg(["median", "min", "max", "count"])
    agg.columns = ["_".join(c) for c in agg.columns]
    return agg.reset_index()


def build_breakeven_rows(records: list[TrialRecord]) -> list[dict]:
    """staging試行(T_stage)とloader試行(epoch_seconds)を突合し損益分岐Eの行を作る。

    結合キー: (node_class, format, cache_state)。staging と loader の cache_state が一致し、
    かつ loader 側の同一条件(num_workers, shuffle_mode, decode)で staging_src と staging_dst
    の両ストレージの計測が揃っている場合のみ、T_epoch_direct(src直読み)と
    T_epoch_staged(dst読み)として比較する。
    """
    from iobench.staging.breakeven import compute_breakeven

    stage_groups: dict[tuple, list[float]] = defaultdict(list)
    for r in records:
        c = r.condition
        if (
            r.subcommand == "staging"
            and r.metrics.t_stage_seconds is not None
            and c.staging_src is not None
            and c.staging_dst is not None
        ):
            key = (
                r.probe.node_class,
                c.format,
                r.cache_state,
                c.staging_tool,
                c.staging_src,
                c.staging_dst,
            )
            stage_groups[key].append(r.metrics.t_stage_seconds)

    # (node_class, format, workers, shuffle, decode, cache_state) -> {storage: [epoch_seconds]}
    epoch_groups: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r.subcommand == "loader" and r.metrics.epoch_seconds is not None:
            c = r.condition
            key = (r.probe.node_class, c.format, c.num_workers, c.shuffle_mode, c.decode, r.cache_state)
            epoch_groups[key][c.storage_logical].append(r.metrics.epoch_seconds)

    rows: list[dict] = []
    for (node_class, fmt, stage_cache_state, tool, src, dst), stages in sorted(stage_groups.items()):
        t_stage = median(stages)
        for (nc, f, workers, shuffle, decode, loader_cache_state), by_storage in sorted(epoch_groups.items()):
            if (nc, f) != (node_class, fmt) or loader_cache_state != stage_cache_state:
                continue
            if src not in by_storage or dst not in by_storage:
                continue
            be = compute_breakeven(t_stage, median(by_storage[src]), median(by_storage[dst]))
            rows.append(
                {
                    "node_class": node_class,
                    "format": fmt,
                    "staging_tool": tool,
                    "staging_src": src,
                    "staging_dst": dst,
                    "num_workers": workers,
                    "shuffle_mode": shuffle,
                    "decode": decode,
                    "cache_state": loader_cache_state,
                    "t_stage_seconds": be.t_stage_seconds,
                    "t_epoch_direct_s": be.t_epoch_direct_seconds,
                    "t_epoch_staged_s": be.t_epoch_ssd_seconds,
                    "per_epoch_saving_s": be.per_epoch_saving_seconds,
                    "breakeven_epochs": be.breakeven_epochs,
                }
            )
    return rows
