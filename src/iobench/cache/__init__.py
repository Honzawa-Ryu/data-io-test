"""ページキャッシュ制御(drop_caches)。権限がない場合はwarm計測を強制記録する。"""

from __future__ import annotations

from iobench.cache.strategies import get_strategy
from iobench.config import CachePolicy
from iobench.results.schema import CacheState

__all__ = ["determine_cache_state"]


def determine_cache_state(
    policy: CachePolicy,
    ram_gb: float,
    dataset_size_bytes: int | None = None,
) -> CacheState:
    """試行前に呼び出す。実際にdrop_cachesを試み、結果に埋めるべき cache_state を返す。

    goal.md 2.3.1: 権限がない場合は (a) データセットサイズ >= RAM*2 の検証、
    または (b) warm計測であることを強制記録する。cold/warmを運用者の裁量で
    偽装できないようにする。
    """
    if policy.mode == "warm":
        return "warm"

    strategy = get_strategy(policy.drop_caches_strategy)
    succeeded = strategy.run()

    if succeeded:
        return "cold"

    # drop_caches不可: サイズ条件でcold相当を主張できるかを検証する
    ram_bytes = ram_gb * (1024**3)
    if dataset_size_bytes is not None and dataset_size_bytes >= ram_bytes * 2:
        return "cold"

    if policy.mode == "cold":
        # coldを要求されたが実現できない: 黙って通さずwarmとして強制記録
        return "warm"

    # mode == "auto"
    return "warm"
