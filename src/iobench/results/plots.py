"""集計結果からグラフを生成する(goal.md 2.5 report)。

- スループット比較(フォーマット×ストレージ)
- シャード/チャンクサイズ掃引カーブ
- 多重負荷劣化
- 損益分岐表(表として出力)

matplotlibはimport時にGUIバックエンドを掴まないよう Agg を明示する。
データが無い系列は静かにスキップし、生成できた図のパス一覧を返す。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def _savefig(fig, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return str(path)


def plot_throughput_comparison(df: pd.DataFrame, out_dir: Path) -> str | None:
    """フォーマット×ストレージのスループット比較(棒グラフ)。"""
    col = "throughput_samples_s_median"
    if df.empty or col not in df.columns or df[col].dropna().empty:
        return None
    pivot = df.pivot_table(index="format", columns="storage_logical", values=col, aggfunc="median")
    fig, ax = plt.subplots(figsize=(8, 5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("throughput (samples/s, median)")
    ax.set_title("Throughput: format x storage")
    ax.legend(title="storage")
    return _savefig(fig, out_dir / "throughput_comparison.png")


def plot_shardsize_sweep(df: pd.DataFrame, out_dir: Path) -> str | None:
    """シャード/チャンクサイズ掃引カーブ(サイズ vs スループット)。"""
    col = "throughput_samples_s_median"
    size_col = "shard_or_chunk_size_bytes"
    if df.empty or size_col not in df.columns or df[size_col].dropna().empty:
        return None
    sub = df.dropna(subset=[size_col, col])
    if sub.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 5))
    for fmt, g in sub.groupby("format"):
        g = g.sort_values(size_col)
        ax.plot(g[size_col] / (1024**2), g[col], marker="o", label=fmt)
    ax.set_xscale("log")
    ax.set_xlabel("shard/chunk size (MB, log)")
    ax.set_ylabel("throughput (samples/s, median)")
    ax.set_title("Shard/chunk size sweep")
    ax.legend()
    return _savefig(fig, out_dir / "shardsize_sweep.png")


def plot_degradation(degradation_rows: list[dict], out_dir: Path) -> str | None:
    """多重負荷劣化率(条件 vs degradation_ratio)。"""
    if not degradation_rows:
        return None
    df = pd.DataFrame(degradation_rows)
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [str(k) for k in df["condition_key"]]
    ax.bar(range(len(df)), df["degradation_ratio"])
    ax.axhline(1.0, color="gray", linestyle="--", label="no degradation (1.0)")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("degradation ratio (multi/baseline)")
    ax.set_title("Multi-load degradation")
    ax.legend()
    return _savefig(fig, out_dir / "degradation.png")


def write_breakeven_table(breakeven_rows: list[dict], out_dir: Path) -> str | None:
    """損益分岐表をCSVで出力する。"""
    if not breakeven_rows:
        return None
    path = out_dir / "breakeven_table.csv"
    pd.DataFrame(breakeven_rows).to_csv(path, index=False)
    return str(path)


def generate_all_plots(
    agg_df: pd.DataFrame,
    out_dir: str,
    degradation_rows: list[dict] | None = None,
    breakeven_rows: list[dict] | None = None,
) -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    for maybe in (
        plot_throughput_comparison(agg_df, out),
        plot_shardsize_sweep(agg_df, out),
        plot_degradation(degradation_rows or [], out),
        write_breakeven_table(breakeven_rows or [], out),
    ):
        if maybe is not None:
            generated.append(maybe)
    return generated
