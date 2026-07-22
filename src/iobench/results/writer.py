"""結果レコードのJSON Lines書き出し・読み込み・cold/warm混在検出。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from iobench.results.schema import TrialRecord


def append_record(record: TrialRecord, jsonl_path: str) -> None:
    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(record.model_dump_json() + "\n")


def load_records(jsonl_path: str) -> list[TrialRecord]:
    records: list[TrialRecord] = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(TrialRecord.model_validate_json(line))
    return records


class MixedCacheStateError(ValueError):
    """同一条件下でcold/warmが混在した比較が検出された。"""


def check_cache_state_consistency(records: list[TrialRecord]) -> None:
    groups: dict[tuple, set[str]] = defaultdict(set)
    for r in records:
        key = (
            r.subcommand,
            r.condition.format,
            r.condition.storage_logical,
            r.probe.node_class,
        )
        groups[key].add(r.cache_state)

    mixed = {k: v for k, v in groups.items() if len(v) > 1}
    if mixed:
        raise MixedCacheStateError(
            f"cold/warmが混在した比較が検出されました(subcommand, format, storage, node_class): {mixed}"
        )


def to_rows(records: list[TrialRecord]) -> list[dict]:
    """集計CSV用にレコードをフラットな辞書へ変換する。"""
    rows = []
    for r in records:
        row = {
            "trial_id": r.trial_id,
            "timestamp": r.timestamp.isoformat(),
            "hostname": r.probe.hostname,
            "node_class": r.probe.node_class,
            "subcommand": r.subcommand,
            "format": r.condition.format,
            "storage_logical": r.condition.storage_logical,
            "shard_or_chunk_size_bytes": r.condition.shard_or_chunk_size_bytes,
            "num_workers": r.condition.num_workers,
            "shuffle_mode": r.condition.shuffle_mode,
            "decode": r.condition.decode,
            "cache_state": r.cache_state,
            "repetition_index": r.repetition_index,
            "repetition_total": r.repetition_total,
            "purpose": r.purpose,
            "library_version": r.library_version,
            **r.metrics.model_dump(),
        }
        rows.append(row)
    return rows
