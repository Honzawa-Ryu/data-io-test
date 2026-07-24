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


# Okabe-Ito(CVD-safe)から採った固定割当。storage=色相(hdd系=暖色, ssd系=寒色)、
# cold=濃 / warm=淡。系列が増減しても色は組に固定(順序で使い回さない)。
_SERIES_COLORS = {
    ("hdd", "cold"): "#D55E00",
    ("hdd", "warm"): "#E69F00",
    ("nfs", "cold"): "#CC79A7",
    ("nfs", "warm"): "#F0E442",
    ("ssd_scratch", "cold"): "#0072B2",
    ("ssd_scratch", "warm"): "#56B4E9",
    ("tmpfs", "cold"): "#009E73",
    ("tmpfs", "warm"): "#8FD9C4",
    ("unified", "cold"): "#000000",
    ("unified", "warm"): "#999999",
}


def plot_staging_throughput(staging_df: pd.DataFrame, out_dir: Path) -> str | None:
    """フォーマット別のステージング転送スループット(棒グラフ)。"""
    if staging_df is None or staging_df.empty:
        return None
    agg = staging_df.groupby("format", dropna=False)["throughput_mb_s"].median().sort_values()
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(agg.index, agg.values, color="#0072B2", height=0.55)
    ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)
    ax.set_xlabel("staging throughput (MB/s, median)")
    ax.set_title("Staging transfer throughput by format")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    return _savefig(fig, out_dir / "staging_throughput.png")


def plot_loader_summary(loader_df: pd.DataFrame, out_dir: Path) -> str | None:
    """loaderのcold/warm×storage比較(num_workers最大・shuffle=shardのグループ棒)。"""
    if loader_df is None or loader_df.empty:
        return None
    sub = loader_df[loader_df["shuffle"] == "shard"]
    if sub.empty:
        return None
    sub = sub[sub["num_workers"] == sub["num_workers"].max()]
    pivot = sub.pivot_table(
        index="format",
        columns=["storage", "cache_state"],
        values="samples_s_median",
        aggfunc="median",
    )
    if pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 5))
    n = len(pivot.columns)
    width = 0.8 / n
    for i, col in enumerate(pivot.columns):
        color = _SERIES_COLORS.get(tuple(col), "#999999")
        xs = [x + (i - (n - 1) / 2) * width for x in range(len(pivot.index))]
        ax.bar(xs, pivot[col].values, width=width * 0.9, color=color, label=f"{col[0]} / {col[1]}")
    ax.set_xticks(range(len(pivot.index)))
    ax.set_xticklabels(pivot.index)
    ax.set_ylabel(f"throughput (samples/s, median, workers={int(sub['num_workers'].max())}, shard)")
    ax.set_title("Loader throughput: storage x cache_state")
    ax.legend(title="storage / cache")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    return _savefig(fig, out_dir / "loader_summary.png")


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
    staging_df: pd.DataFrame | None = None,
    loader_df: pd.DataFrame | None = None,
) -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    for maybe in (
        plot_throughput_comparison(agg_df, out),
        plot_shardsize_sweep(agg_df, out),
        plot_degradation(degradation_rows or [], out),
        write_breakeven_table(breakeven_rows or [], out),
        plot_staging_throughput(staging_df, out),
        plot_loader_summary(loader_df, out),
    ):
        if maybe is not None:
            generated.append(maybe)
    return generated
