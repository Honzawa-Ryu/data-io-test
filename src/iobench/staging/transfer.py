"""転送計測: cp / rsync / tarパイプ / シャード単位並列rsync × bwlimit有無。"""

from __future__ import annotations

import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TransferResult:
    tool: str
    src: str
    dst: str
    total_bytes: int
    elapsed_seconds: float
    throughput_mb_s: float
    bwlimit: str | None


def _dir_size_bytes(path: str) -> int:
    p = Path(path)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def transfer_cp(src: str, dst: str) -> None:
    Path(dst).mkdir(parents=True, exist_ok=True)
    _run(["cp", "-r", src, dst])


def transfer_rsync(src: str, dst: str, bwlimit: str | None = None) -> None:
    Path(dst).mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a"]
    if bwlimit:
        cmd.append(f"--bwlimit={bwlimit}")
    # 末尾スラッシュで中身をコピー
    cmd += [src.rstrip("/") + "/", dst.rstrip("/") + "/"]
    _run(cmd)


def transfer_tar_pipe(src: str, dst: str) -> None:
    """tar -C src -cf - . | tar -C dst -xf - (小ファイル大量時にrsyncより速いことがある)。"""
    Path(dst).mkdir(parents=True, exist_ok=True)
    src_tar = subprocess.Popen(["tar", "-C", src, "-cf", "-", "."], stdout=subprocess.PIPE)
    dst_tar = subprocess.Popen(["tar", "-C", dst, "-xf", "-"], stdin=src_tar.stdout)
    if src_tar.stdout:
        src_tar.stdout.close()
    dst_tar.communicate()
    src_tar.wait()
    if dst_tar.returncode != 0 or src_tar.returncode != 0:
        raise subprocess.CalledProcessError(dst_tar.returncode or src_tar.returncode, "tar pipe")


def transfer_parallel_rsync(src: str, dst: str, bwlimit: str | None = None, parallel: int = 4) -> None:
    """src直下のエントリ(シャード)単位でrsyncを並列実行する。"""
    Path(dst).mkdir(parents=True, exist_ok=True)
    entries = sorted(Path(src).iterdir())

    def _one(entry: Path) -> None:
        cmd = ["rsync", "-a"]
        if bwlimit:
            cmd.append(f"--bwlimit={bwlimit}")
        cmd += [str(entry), dst.rstrip("/") + "/"]
        _run(cmd)

    with ThreadPoolExecutor(max_workers=parallel) as ex:
        list(ex.map(_one, entries))


_TOOLS = {
    "cp": lambda s, d, bw: transfer_cp(s, d),
    "rsync": transfer_rsync,
    "tar": lambda s, d, bw: transfer_tar_pipe(s, d),
    "parallel_rsync": transfer_parallel_rsync,
}


def run_transfer(tool: str, src: str, dst: str, bwlimit: str | None = None) -> TransferResult:
    if tool not in _TOOLS:
        raise ValueError(f"未知の転送ツール: {tool!r}。利用可能: {list(_TOOLS)}")
    for exe in (["cp"] if tool == "cp" else [tool.split("_")[-1]]):
        if shutil.which(exe) is None:
            raise RuntimeError(f"転送コマンド '{exe}' が見つかりません。")

    total_bytes = _dir_size_bytes(src)
    t0 = time.perf_counter()
    _TOOLS[tool](src, dst, bwlimit)
    elapsed = time.perf_counter() - t0
    throughput = (total_bytes / (1024**2)) / elapsed if elapsed > 0 else 0.0

    return TransferResult(
        tool=tool,
        src=src,
        dst=dst,
        total_bytes=total_bytes,
        elapsed_seconds=elapsed,
        throughput_mb_s=throughput,
        bwlimit=bwlimit,
    )
