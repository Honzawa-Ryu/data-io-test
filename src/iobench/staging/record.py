"""staging転送計測をTrialRecordへ変換し、loader結果と同じJSONLパイプラインに乗せる。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from iobench.results.schema import (
    CacheState,
    Condition,
    FormatName,
    Metrics,
    ProbeResult,
    Purpose,
    StorageLogical,
    TrialRecord,
)
from iobench.staging.transfer import TransferResult


def resolve_storage_logical(path: str, resolved_paths: dict[str, str]) -> str | None:
    """実パスがどの論理ストレージ配下かを最長一致で解決する。該当なしはNone。"""
    target = Path(path).absolute()
    best: tuple[int, str] | None = None
    for logical, root in resolved_paths.items():
        root_p = Path(root).absolute()
        if target == root_p or root_p in target.parents:
            depth = len(root_p.parts)
            if best is None or depth > best[0]:
                best = (depth, logical)
    return best[1] if best else None


def build_staging_record(
    result: TransferResult,
    probe: ProbeResult,
    *,
    fmt: FormatName,
    cache_state: CacheState,
    purpose: Purpose,
    library_version: str,
    src_logical: StorageLogical | None = None,
    dst_logical: StorageLogical | None = None,
) -> TrialRecord:
    """転送結果からTrialRecordを組み立てる。論理名は未指定ならresolved_pathsから解決する。"""
    src = src_logical or resolve_storage_logical(result.src, probe.resolved_paths)
    dst = dst_logical or resolve_storage_logical(result.dst, probe.resolved_paths)
    if src is None or dst is None:
        missing = "src" if src is None else "dst"
        path = result.src if src is None else result.dst
        raise ValueError(
            f"{missing}のパス '{path}' がresolved_paths({probe.resolved_paths})のどの論理ストレージ"
            f"配下にも一致しません。--{missing}-logical で明示してください。"
        )

    return TrialRecord(
        trial_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        probe=probe,
        condition=Condition(
            format=fmt,
            storage_logical=dst,
            num_workers=0,
            shuffle_mode="none",
            decode=False,
            staging_tool=result.tool,
            staging_src=src,
            staging_dst=dst,
        ),
        metrics=Metrics(
            t_stage_seconds=result.elapsed_seconds,
            throughput_mb_s=result.throughput_mb_s,
            staged_bytes=result.total_bytes,
        ),
        cache_state=cache_state,
        repetition_index=0,
        repetition_total=1,
        library_version=library_version,
        purpose=purpose,
        subcommand="staging",
        notes=f"bwlimit={result.bwlimit}" if result.bwlimit else None,
    )
