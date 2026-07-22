"""fioプリセット定義: シーケンシャル/ランダム × ブロックサイズ × iodepth × numjobs。"""

from __future__ import annotations

from typing import Iterator, TypedDict


class FioPreset(TypedDict):
    name: str
    rw: str
    bs: str
    iodepth: int
    numjobs: int


BLOCK_SIZES = ["4k", "128k", "1m", "16m"]
IODEPTHS = [1, 32]
NUMJOBS = [1, 8]
PATTERNS = {"seq": "read", "rand": "randread"}


def iter_presets() -> Iterator[FioPreset]:
    for pattern, rw in PATTERNS.items():
        for bs in BLOCK_SIZES:
            for iodepth in IODEPTHS:
                for numjobs in NUMJOBS:
                    yield FioPreset(
                        name=f"{pattern}_{bs}_qd{iodepth}_nj{numjobs}",
                        rw=rw,
                        bs=bs,
                        iodepth=iodepth,
                        numjobs=numjobs,
                    )


def get_preset(name: str) -> FioPreset:
    for preset in iter_presets():
        if preset["name"] == name:
            return preset
    raise ValueError(f"未知のfioプリセット: {name!r}")


NFS_SMALLFILE_PRESET = {
    "name": "nfs_smallfile_stat_read",
    "file_count": 10000,
    "file_size_bytes": 4096,
}
