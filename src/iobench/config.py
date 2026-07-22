"""クラスタ設定(nodes.yaml)と実験定義YAMLのスキーマ。

docs/design.md 4節のレビュー対象。読み込み・検証ロジックはフェーズ2で実装する
(本ファイルはスキーマのみ)。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from iobench.results.schema import FormatName, ShuffleMode, StorageLogical


class NodeClassMatch(BaseModel):
    partition: list[str] = []
    hostname_pattern: str | None = None
    constraint: list[str] = []


class NodeClassConfig(BaseModel):
    match: NodeClassMatch
    paths: dict[str, str | None] = {}
    unified_memory: bool = False


class NodesConfig(BaseModel):
    """configs/nodes.yaml のトップレベルスキーマ。"""

    node_classes: dict[Literal["X", "Y", "Z"], NodeClassConfig]


class CachePolicy(BaseModel):
    mode: Literal["cold", "warm", "auto"] = "cold"
    drop_caches_strategy: str = "sudo_tee"


class ExperimentMatrix(BaseModel):
    format: list[FormatName] = []
    storage: list[StorageLogical] = []
    num_workers: list[int] = []
    shuffle_mode: list[ShuffleMode] = []
    decode: list[bool] = [True]


class DatasetRef(BaseModel):
    ref: str
    shard_size_bytes: int | None = None
    chunk_size_bytes: int | None = None


class OutputConfig(BaseModel):
    jsonl: str = "results/trials.jsonl"
    purpose_tag: Literal["dev", "campaign"] = "dev"


class ExperimentConfig(BaseModel):
    """実験定義YAML(loader/staging/multi向け)のトップレベルスキーマ。"""

    purpose: Literal["dev", "campaign"] = "dev"
    repetitions: int = 3
    cache_policy: CachePolicy = CachePolicy()
    matrix: ExperimentMatrix
    dataset: DatasetRef
    output: OutputConfig = OutputConfig()
