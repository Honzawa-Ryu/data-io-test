"""結果JSONLからの集計(中央値・min・max)。グラフ生成は今後のフェーズで拡張する。"""

from __future__ import annotations

import pandas as pd

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
]

METRIC_KEYS = [
    "throughput_samples_s",
    "throughput_mb_s",
    "gpu_idle_ratio",
    "t_stage_seconds",
    "first_batch_latency_s",
    "degradation_ratio",
    "meta_ops_s",
]


def aggregate(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    agg = df.groupby(GROUP_KEYS, dropna=False)[METRIC_KEYS].agg(["median", "min", "max", "count"])
    agg.columns = ["_".join(c) for c in agg.columns]
    return agg.reset_index()
