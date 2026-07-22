"""fioをサブプロセスとして実行し、JSON出力を Metrics 相当の辞書に正規化する。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from iobench.storage.presets import FioPreset


class FioNotFoundError(RuntimeError):
    """fioがOSに導入されていない。"""


def run_fio(preset: FioPreset, target_dir: str, runtime_sec: int = 10, size: str = "1G") -> dict:
    if shutil.which("fio") is None:
        raise FioNotFoundError(
            "fio が見つかりません。計算ノードに `apt-get install fio` 等で導入してください。"
        )
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    testfile = str(Path(target_dir) / f"iobench_fio_{preset['name']}")
    cmd = [
        "fio",
        f"--name={preset['name']}",
        f"--filename={testfile}",
        f"--rw={preset['rw']}",
        f"--bs={preset['bs']}",
        f"--iodepth={preset['iodepth']}",
        f"--numjobs={preset['numjobs']}",
        "--direct=1",
        f"--runtime={runtime_sec}",
        "--time_based",
        f"--size={size}",
        "--group_reporting",
        "--output-format=json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def parse_fio_result(raw: dict) -> dict:
    job = raw["jobs"][0]
    read = job.get("read", {}) or {}
    write = job.get("write", {}) or {}
    bw_kb_s = (read.get("bw") or 0) + (write.get("bw") or 0)
    iops = (read.get("iops") or 0) + (write.get("iops") or 0)
    return {
        "throughput_mb_s": bw_kb_s / 1024.0,
        "iops": iops,
    }
