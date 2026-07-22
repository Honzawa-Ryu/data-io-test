from iobench.cache import determine_cache_state
from iobench.config import CachePolicy


def test_warm_mode_always_warm():
    policy = CachePolicy(mode="warm")
    assert determine_cache_state(policy, ram_gb=64.0) == "warm"


def test_cold_mode_without_permission_and_small_dataset_forces_warm():
    policy = CachePolicy(mode="cold", drop_caches_strategy="noop")
    # データセットがRAM*2未満なので、drop_caches不可ならwarmを強制
    state = determine_cache_state(policy, ram_gb=64.0, dataset_size_bytes=1024)
    assert state == "warm"


def test_cold_mode_without_permission_but_large_dataset_allows_cold():
    policy = CachePolicy(mode="cold", drop_caches_strategy="noop")
    ram_gb = 1.0
    large_dataset = int(ram_gb * (1024**3) * 3)  # RAM*2以上
    state = determine_cache_state(policy, ram_gb=ram_gb, dataset_size_bytes=large_dataset)
    assert state == "cold"


def test_external_strategy_records_cold():
    # 手動drop運用: ライブラリはdropしないが、外部で落とされた前提でcold記録
    policy = CachePolicy(mode="cold", drop_caches_strategy="external")
    state = determine_cache_state(policy, ram_gb=64.0, dataset_size_bytes=1024)
    assert state == "cold"
