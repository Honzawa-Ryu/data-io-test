"""shuffle_mode の実挙動を定義する。goal.md 4節「同じ設定なら比較可能」を守るため、
各フォーマットで none/shard/full が必ず別々の realized behavior になるようにする。

- none  : シャッフルなし(逐次)
- shard : シャード内(ブロック内)シャッフル。読み出しの局所性を保ったままブロック内だけ並べ替える。
          map系はブロック内シャッフル、webdatasetはシャード順シャッフル+シャッフルバッファ。
- full  : 完全ランダム。全サンプルの大域置換。webdataset(tar逐次)では実現不能なので展開時にスキップ。
"""

from __future__ import annotations

import numpy as np
from torch.utils.data import Sampler


class WebdatasetFullShuffleUnsupported(RuntimeError):
    """webdatasetはtar逐次構造のため真の完全ランダムアクセスを実現できない。"""


def block_local_order(n: int, block_size: int, seed: int) -> list[int]:
    """[0,n) をblock_size毎のブロックに切り、ブロック順は保ちつつブロック内をシャッフルした順序を返す。"""
    rng = np.random.default_rng(seed)
    order: list[int] = []
    for start in range(0, n, block_size):
        blk = list(range(start, min(start + block_size, n)))
        rng.shuffle(blk)
        order.extend(blk)
    return order


def full_order(n: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    perm = list(range(n))
    rng.shuffle(perm)
    return perm


class OrderSampler(Sampler[int]):
    """あらかじめ計算したインデックス順を返すだけのSampler。"""

    def __init__(self, order: list[int]) -> None:
        self._order = order

    def __iter__(self):
        return iter(self._order)

    def __len__(self) -> int:
        return len(self._order)


def make_map_sampler(
    n: int, shuffle_mode: str, seed: int, block_size: int
) -> OrderSampler | None:
    """map系Dataset用のSamplerを返す。noneはNone(DataLoaderの逐次読みに任せる)。"""
    if shuffle_mode == "none":
        return None
    if shuffle_mode == "shard":
        return OrderSampler(block_local_order(n, block_size, seed))
    if shuffle_mode == "full":
        return OrderSampler(full_order(n, seed))
    raise ValueError(f"未知のshuffle_mode: {shuffle_mode!r}")


def buffered_shuffle(iterable, bufsize: int, seed: int):
    """streaming用シャッフルバッファ。bufsize件を貯めてランダムに1件ずつ吐き出す。"""
    if bufsize <= 1:
        yield from iterable
        return
    rng = np.random.default_rng(seed)
    buf: list = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= bufsize:
            j = rng.integers(0, len(buf))
            buf[j], buf[-1] = buf[-1], buf[j]
            yield buf.pop()
    rng.shuffle(buf)
    yield from buf
