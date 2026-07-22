"""多重負荷試験の集計: N本同時実行時のスループット劣化率を単独実行と突合して算出する。

ジョブ投入自体はslurmモジュール(またはrun_loaderのsbatchを-w同一ノードにN本)が担い、
本モジュールは結果JSONLから degradation_ratio を計算する集計器。
"""

from __future__ import annotations

from dataclasses import dataclass

from iobench.results.schema import TrialRecord


@dataclass
class DegradationResult:
    condition_key: tuple
    baseline_samples_s: float
    multi_samples_s_mean: float
    concurrency: int
    degradation_ratio: float  # 1.0=劣化なし, 0.5=半減


def _cond_key(r: TrialRecord) -> tuple:
    return (
        r.condition.format,
        r.condition.storage_logical,
        r.condition.num_workers,
        r.condition.shuffle_mode,
        r.condition.decode,
        r.probe.node_class,
    )


def compute_degradation(
    baseline_records: list[TrialRecord],
    multi_records: list[TrialRecord],
) -> list[DegradationResult]:
    """baseline(単独実行) と multi(N本同時) を条件ごとに突合し劣化率を出す。

    degradation_ratio = multi時の平均スループット / baseline時のスループット。
    """
    results: list[DegradationResult] = []

    # baselineは条件ごとに中央値相当(単純平均)を代表値にする
    base_by_key: dict[tuple, list[float]] = {}
    for r in baseline_records:
        if r.metrics.throughput_samples_s is not None:
            base_by_key.setdefault(_cond_key(r), []).append(r.metrics.throughput_samples_s)

    multi_by_key: dict[tuple, list[float]] = {}
    for r in multi_records:
        if r.metrics.throughput_samples_s is not None:
            multi_by_key.setdefault(_cond_key(r), []).append(r.metrics.throughput_samples_s)

    for key, multi_vals in multi_by_key.items():
        if key not in base_by_key:
            continue
        baseline = sum(base_by_key[key]) / len(base_by_key[key])
        multi_mean = sum(multi_vals) / len(multi_vals)
        ratio = multi_mean / baseline if baseline > 0 else 0.0
        results.append(
            DegradationResult(
                condition_key=key,
                baseline_samples_s=baseline,
                multi_samples_s_mean=multi_mean,
                concurrency=len(multi_vals),
                degradation_ratio=ratio,
            )
        )
    return results
