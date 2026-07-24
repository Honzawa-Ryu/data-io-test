"""パイプライン全体のまとめ: storage/staging/loader/breakeven の各表と summary.md を生成する。"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from iobench.results.schema import StorageTrialRecord, TrialRecord


def staging_table(records: list[TrialRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        if r.subcommand != "staging":
            continue
        c, m = r.condition, r.metrics
        rows.append(
            {
                "format": c.format,
                "tool": c.staging_tool,
                "src": c.staging_src,
                "dst": c.staging_dst,
                "size_gb": round((m.staged_bytes or 0) / 1e9, 2),
                "t_stage_s": round(m.t_stage_seconds or 0.0, 1),
                "throughput_mb_s": round(m.throughput_mb_s or 0.0, 1),
                "cache_state": r.cache_state,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["format", "src", "dst", "tool"]).reset_index(drop=True)
    return df


def loader_table(records: list[TrialRecord]) -> pd.DataFrame:
    """loader試行を条件ごとに集計(中央値+試行数)。"""
    rows = []
    for r in records:
        if r.subcommand != "loader":
            continue
        c, m = r.condition, r.metrics
        rows.append(
            {
                "format": c.format,
                "storage": c.storage_logical,
                "num_workers": c.num_workers,
                "shuffle": c.shuffle_mode,
                "cache_state": r.cache_state,
                "samples_s": m.throughput_samples_s,
                "epoch_s": m.epoch_seconds,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    keys = ["format", "storage", "num_workers", "shuffle", "cache_state"]
    agg = df.groupby(keys, dropna=False).agg(
        samples_s_median=("samples_s", "median"),
        epoch_s_median=("epoch_s", "median"),
        n=("samples_s", "count"),
    )
    agg = agg.reset_index().sort_values(keys).reset_index(drop=True)
    agg["samples_s_median"] = agg["samples_s_median"].round(0)
    agg["epoch_s_median"] = agg["epoch_s_median"].round(1)
    return agg


def storage_table(records: list[StorageTrialRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append(
            {
                "target": r.target_logical or r.target,
                "preset": r.preset,
                **{k: round(v, 1) for k, v in r.metrics.items()},
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["target", "preset"]).reset_index(drop=True)
    return df


def _md_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_(データなし)_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def render_summary_md(
    *,
    node_label: str,
    storage_df: pd.DataFrame,
    staging_df: pd.DataFrame,
    loader_df: pd.DataFrame,
    breakeven_df: pd.DataFrame,
) -> str:
    """パイプライン一巡(storage→staging→loader→breakeven)の単一まとめドキュメント。"""
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    if breakeven_df is not None and not breakeven_df.empty:
        breakeven_df = breakeven_df.round(1)
    cold = loader_df[loader_df["cache_state"] == "cold"] if not loader_df.empty else loader_df
    warm = loader_df[loader_df["cache_state"] == "warm"] if not loader_df.empty else loader_df
    sections = [
        f"# iobench パイプラインまとめ({node_label})",
        f"生成: {now}",
        "",
        "## 1. ストレージ素性(fio / smallfile)",
        _md_table(storage_df)
        if storage_df is not None and not storage_df.empty
        else "_(未計測。`iobench storage --target ... --preset ...` を実行すると "
        "results/trials_storage.jsonl に記録され、ここに表示される)_",
        "",
        "## 2. ステージング転送(T_stage)",
        _md_table(staging_df),
        "",
        "## 3. Loader スループット(cold)",
        _md_table(cold),
        "",
        "## 4. Loader スループット(warm)",
        _md_table(warm),
        "",
        "## 5. 損益分岐エポック数 E(T_stage vs エポック時間差)",
        _md_table(breakeven_df),
        "",
        "> E=1: 1エポックでもステージングが得。空欄/データなし: 対応する cold loader 計測が未実施。",
        "",
    ]
    return "\n".join(sections)
