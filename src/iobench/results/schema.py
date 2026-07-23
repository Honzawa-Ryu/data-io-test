"""結果レコードのスキーマ定義。

docs/design.md 3節のレビュー対象。フィールド追加/変更はここと design.md を両方更新する。
JSON Lines書き出し・集計ロジックはフェーズ2で実装する(本ファイルはスキーマのみ)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

StorageLogical = Literal["nfs", "hdd", "ssd_scratch", "tmpfs", "unified"]
FormatName = Literal["raw", "webdataset", "hdf5", "zarr_v3", "zarr_v2"]
ShuffleMode = Literal["none", "shard", "full"]
CacheState = Literal["cold", "warm"]
Purpose = Literal["dev", "campaign"]
Subcommand = Literal["storage", "datagen", "loader", "staging", "multi"]


class MountInfo(BaseModel):
    path: str
    fs_type: str
    device: str | None = None
    rotational: bool | None = None
    is_nvme: bool = False


class ProbeResult(BaseModel):
    hostname: str
    node_class: str
    slurm_job_id: str | None = None
    slurm_partition: str | None = None
    slurm_tmpdir: str | None = None
    mounts: list[MountInfo] = []
    cpu_cores: int
    ram_gb: float
    gpu_present: bool
    gpu_model: str | None = None
    unified_memory: bool = False
    resolved_paths: dict[str, str] = {}


class Condition(BaseModel):
    format: FormatName
    storage_logical: StorageLogical
    shard_or_chunk_size_bytes: int | None = None
    num_workers: int
    shuffle_mode: ShuffleMode
    decode: bool


class Metrics(BaseModel):
    throughput_samples_s: float | None = None
    throughput_mb_s: float | None = None
    gpu_idle_ratio: float | None = None
    t_stage_seconds: float | None = None
    first_batch_latency_s: float | None = None
    degradation_ratio: float | None = None
    meta_ops_s: float | None = None


class TrialRecord(BaseModel):
    trial_id: str
    timestamp: datetime
    probe: ProbeResult
    condition: Condition
    metrics: Metrics
    cache_state: CacheState
    repetition_index: int
    repetition_total: int
    library_version: str
    purpose: Purpose
    subcommand: Subcommand
    sidecar_ref: str | None = None
    notes: str | None = None
