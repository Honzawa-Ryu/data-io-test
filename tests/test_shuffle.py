import pytest

from iobench.loaderbench.shuffle import (
    block_local_order,
    buffered_shuffle,
    full_order,
    make_map_sampler,
)


def test_block_local_keeps_block_order_but_shuffles_within():
    order = block_local_order(10, block_size=5, seed=0)
    # 全インデックスが1回ずつ
    assert sorted(order) == list(range(10))
    # 前半ブロックの要素は{0..4}、後半は{5..9}(ブロック順は保たれる)
    assert set(order[:5]) == {0, 1, 2, 3, 4}
    assert set(order[5:]) == {5, 6, 7, 8, 9}


def test_none_shard_full_are_distinct_orders():
    n = 100
    none_order = list(range(n))
    shard = block_local_order(n, block_size=10, seed=0)
    full = full_order(n, seed=0)
    # 3モードがすべて異なる順序になる(比較可能性の担保)
    assert none_order != shard
    assert shard != full
    assert none_order != full
    # shardは局所シャッフルなのでfullより「元の位置からのズレ」が小さい
    shard_disp = sum(abs(i - shard[i]) for i in range(n))
    full_disp = sum(abs(i - full[i]) for i in range(n))
    assert shard_disp < full_disp


def test_make_map_sampler_none_returns_none():
    assert make_map_sampler(10, "none", seed=0, block_size=5) is None


def test_make_map_sampler_shard_and_full_cover_all_indices():
    for mode in ("shard", "full"):
        sampler = make_map_sampler(20, mode, seed=1, block_size=5)
        assert sorted(list(sampler)) == list(range(20))


def test_buffered_shuffle_preserves_multiset():
    items = list(range(50))
    out = list(buffered_shuffle(iter(items), bufsize=8, seed=0))
    assert sorted(out) == items
    # バッファシャッフルなので順序は変わる
    assert out != items
