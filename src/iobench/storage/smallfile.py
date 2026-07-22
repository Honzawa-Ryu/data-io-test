"""NFS向け小ファイル大量stat/read計測。fioのファイル生成系プラグインに依存せず自前実装する。"""

from __future__ import annotations

import os
import time
from pathlib import Path


def run_smallfile_benchmark(
    target_dir: str,
    file_count: int = 10000,
    file_size_bytes: int = 4096,
) -> dict:
    d = Path(target_dir) / "iobench_smallfile"
    d.mkdir(parents=True, exist_ok=True)
    payload = os.urandom(file_size_bytes)
    paths = [d / f"f{i:07d}.bin" for i in range(file_count)]

    t0 = time.perf_counter()
    for p in paths:
        p.write_bytes(payload)
    write_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    for p in paths:
        p.stat()
    stat_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    for p in paths:
        p.read_bytes()
    read_elapsed = time.perf_counter() - t0

    for p in paths:
        p.unlink()
    d.rmdir()

    return {
        "write_ops_s": file_count / write_elapsed if write_elapsed > 0 else None,
        "meta_ops_s": file_count / stat_elapsed if stat_elapsed > 0 else None,
        "read_ops_s": file_count / read_elapsed if read_elapsed > 0 else None,
    }
