"""実験定義YAMLを展開し、反復・cache制御・sidecar・結果記録を統合してloader計測を回す。"""

from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timezone
from pathlib import Path

from iobench.cache import determine_cache_state
from iobench.config import ExperimentConfig
from iobench.gitinfo import get_git_hash
from iobench.loaderbench.bench import run_loader_epoch
from iobench.probe import run_probe
from iobench.config import NodesConfig
from iobench.results.schema import Condition, Metrics, ProbeResult, TrialRecord
from iobench.results.writer import append_record
from iobench.sidecar import SidecarSession


def _dataset_path(base: Path, fmt: str) -> str:
    """datagenの出力レイアウトに対応してフォーマット別の実パスを決める。"""
    if fmt == "zarr_v3":
        return str(base / "v3.zarr")
    if fmt == "zarr_v2":
        return str(base / "v2_reference.zarr")
    return str(base)


def _dataset_size_bytes(path: str) -> int | None:
    """cache判定(データセット≥RAM×2ならcold相当)のためデータセット総サイズを測る。"""
    p = Path(path)
    if not p.exists():
        return None
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def iter_conditions(cfg: ExperimentConfig):
    m = cfg.matrix
    for fmt, storage, workers, shuffle, decode in itertools.product(
        m.format, m.storage, m.num_workers, m.shuffle_mode, m.decode
    ):
        yield Condition(
            format=fmt,
            storage_logical=storage,
            shard_or_chunk_size_bytes=cfg.dataset.shard_size_bytes or cfg.dataset.chunk_size_bytes,
            num_workers=workers,
            shuffle_mode=shuffle,
            decode=decode,
        )


def run_experiment(
    cfg: ExperimentConfig,
    nodes_config: NodesConfig,
    dataset_root: str,
    *,
    batch_size: int = 32,
    to_gpu: bool = False,
    force_node_class: str | None = None,
) -> list[TrialRecord]:
    probe: ProbeResult = run_probe(nodes_config, force_node_class=force_node_class)
    version = get_git_hash()
    records: list[TrialRecord] = []

    # 手動drop運用(external)は最初の読みだけがcold。反復2回目以降は実際にはwarmなのに
    # cold記録されてしまうため、repetitions>1と併用しないよう警告する。
    if cfg.cache_policy.drop_caches_strategy == "external" and cfg.repetitions > 1:
        print(
            f"[warning] drop_caches_strategy='external'(手動drop運用)で repetitions={cfg.repetitions} です。"
            "手動dropは最初の1試行のみをcoldにします。cold試行はrepetitions=1にして、"
            "投入前に毎回手動dropした別ジョブとして回してください(docs/howto.md参照)。"
        )

    for condition in iter_conditions(cfg):
        # webdatasetは真の完全ランダム(full)を実現できないので、崩れた比較を記録せずスキップする。
        if condition.format == "webdataset" and condition.shuffle_mode == "full":
            print(
                "[skip] webdataset × shuffle_mode=full は実現不能(tar逐次)のためスキップします。"
                "完全ランダムは map系フォーマットで測定してください。"
            )
            continue

        storage_path = probe.resolved_paths.get(condition.storage_logical)
        if storage_path is None:
            raise ValueError(
                f"論理ストレージ '{condition.storage_logical}' が現ノード({probe.node_class})の"
                f"resolved_pathsに存在しません。configs/nodes.yaml を確認してください。"
            )
        base = Path(storage_path) / dataset_root
        path = _dataset_path(base, condition.format)
        dataset_size = _dataset_size_bytes(path)

        for rep in range(cfg.repetitions):
            cache_state = determine_cache_state(cfg.cache_policy, probe.ram_gb, dataset_size)
            trial_id = str(uuid.uuid4())

            with SidecarSession(trial_id, gpu_present=probe.gpu_present) as sc:
                result = run_loader_epoch(
                    condition.format,
                    path,
                    decode=condition.decode,
                    shuffle_mode=condition.shuffle_mode,
                    num_workers=condition.num_workers,
                    batch_size=batch_size,
                    seed=rep,
                    to_gpu=to_gpu,
                )
                sidecar_ref = sc.ref

            record = TrialRecord(
                trial_id=trial_id,
                timestamp=datetime.now(timezone.utc),
                probe=probe,
                condition=condition,
                metrics=Metrics(
                    throughput_samples_s=result.throughput_samples_s,
                    throughput_mb_s=result.throughput_mb_s,
                    gpu_idle_ratio=result.gpu_idle_ratio,
                    first_batch_latency_s=result.first_batch_latency_s,
                    epoch_seconds=result.elapsed_seconds,
                ),
                cache_state=cache_state,
                repetition_index=rep,
                repetition_total=cfg.repetitions,
                library_version=version,
                purpose=cfg.purpose,
                subcommand="loader",
                sidecar_ref=sidecar_ref,
            )
            append_record(record, cfg.output.jsonl)
            records.append(record)

    return records
