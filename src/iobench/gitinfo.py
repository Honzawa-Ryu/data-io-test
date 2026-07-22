"""結果レコードに埋める library_version(gitハッシュ)の取得。"""

from __future__ import annotations

import subprocess


def get_git_hash(short: bool = True) -> str:
    cmd = ["git", "rev-parse"]
    if short:
        cmd.append("--short")
    cmd.append("HEAD")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
