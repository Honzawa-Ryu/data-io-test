"""fioラッパによるストレージ素性計測(シーケンシャル/ランダム×ブロックサイズ×iodepth×numjobs)。"""

from iobench.storage.fio_runner import (
    FioNotFoundError,
    build_fio_command,
    parse_fio_result,
    run_fio,
)
from iobench.storage.presets import NFS_SMALLFILE_PRESET, get_preset, iter_presets
from iobench.storage.smallfile import run_smallfile_benchmark

__all__ = [
    "FioNotFoundError",
    "run_fio",
    "build_fio_command",
    "parse_fio_result",
    "iter_presets",
    "get_preset",
    "NFS_SMALLFILE_PRESET",
    "run_smallfile_benchmark",
]
