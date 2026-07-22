"""実行ノードから素の環境情報(fact)を収集する。分類ロジックは classify.py 側。"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import psutil

from iobench.results.schema import MountInfo

_VIRTUAL_FS_TYPES = {
    "proc",
    "sysfs",
    "cgroup",
    "cgroup2",
    "devtmpfs",
    "overlay",
    "devpts",
    "mqueue",
    "securityfs",
    "pstore",
    "bpf",
    "tracefs",
    "debugfs",
    "hugetlbfs",
    "configfs",
    "fusectl",
    "autofs",
    "binfmt_misc",
}


def get_hostname() -> str:
    return socket.gethostname()


def get_slurm_env() -> dict[str, str | None]:
    return {
        "job_id": os.environ.get("SLURM_JOB_ID"),
        "partition": os.environ.get("SLURM_JOB_PARTITION"),
        "tmpdir": os.environ.get("SLURM_TMPDIR"),
        "constraint": os.environ.get("SLURM_JOB_CONSTRAINT", ""),
    }


def _rotational_flag(devname: str) -> bool | None:
    sys_path = Path(f"/sys/block/{devname}/queue/rotational")
    if not sys_path.exists():
        return None
    try:
        return sys_path.read_text().strip() == "1"
    except OSError:
        return None


def _resolve_block_device_name(device_path: str) -> str | None:
    """'/dev/sda1' -> 'sda', '/dev/nvme0n1p1' -> 'nvme0n1' のように親ブロックデバイス名を得る。"""
    name = os.path.basename(device_path)
    if name.startswith("nvme"):
        m = re.match(r"(nvme\d+n\d+)", name)
        return m.group(1) if m else name
    m = re.match(r"([a-zA-Z]+)\d*", name)
    return m.group(1) if m else name


def list_mounts() -> list[MountInfo]:
    """/proc/mounts を解析し、意味のあるマウント一覧を返す。"""
    mounts: list[MountInfo] = []
    try:
        raw_lines = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        return mounts

    for line in raw_lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mountpoint, fstype = parts[0], parts[1], parts[2]
        if fstype in _VIRTUAL_FS_TYPES:
            continue

        rotational: bool | None = None
        is_nvme = False
        resolved_device: str | None = None
        if fstype.startswith("nfs"):
            resolved_device = device
        elif device.startswith("/dev/"):
            resolved_device = device
            block_name = _resolve_block_device_name(device)
            if block_name:
                rotational = _rotational_flag(block_name)
                is_nvme = block_name.startswith("nvme")

        mounts.append(
            MountInfo(
                path=mountpoint,
                fs_type=fstype,
                device=resolved_device,
                rotational=rotational,
                is_nvme=is_nvme,
            )
        )
    return mounts


def get_cpu_cores() -> int:
    return psutil.cpu_count(logical=True) or os.cpu_count() or 0


def get_ram_gb() -> float:
    return psutil.virtual_memory().total / (1024**3)


def get_gpu_info() -> tuple[bool, str | None]:
    try:
        import torch

        if torch.cuda.is_available():
            return True, torch.cuda.get_device_name(0)
    except Exception:
        pass
    return False, None
