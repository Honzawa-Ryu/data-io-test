"""結果スキーマ定義、JSON Lines書き出し、集計CSV生成。"""

from iobench.results.report import aggregate
from iobench.results.schema import Condition, Metrics, MountInfo, ProbeResult, TrialRecord
from iobench.results.writer import (
    MixedCacheStateError,
    append_record,
    check_cache_state_consistency,
    load_records,
    to_rows,
)

__all__ = [
    "Condition",
    "Metrics",
    "MountInfo",
    "ProbeResult",
    "TrialRecord",
    "MixedCacheStateError",
    "append_record",
    "check_cache_state_consistency",
    "load_records",
    "to_rows",
    "aggregate",
]
