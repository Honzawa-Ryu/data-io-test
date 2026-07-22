"""sbatchテンプレート生成・投入・依存関係管理。ステージング運用パターンA/B/Cを実装する。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from iobench.slurm.templates import render_pattern_a, render_pattern_b, render_pattern_c

__all__ = ["dataset_hash", "write_pattern", "render_pattern_a", "render_pattern_b", "render_pattern_c"]


def dataset_hash(dataset_ref: str, extra: str = "") -> str:
    """パターンC共有キャッシュのディレクトリ名に使う安定ハッシュ。"""
    return hashlib.sha256(f"{dataset_ref}|{extra}".encode()).hexdigest()[:16]


def _write(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def write_pattern(pattern: str, out_dir: str, **kwargs) -> list[str]:
    """指定パターンのsbatchスクリプト群を out_dir に書き出し、生成したパスの一覧を返す。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    if pattern == "A":
        p = out / "stageA.sh"
        _write(p, render_pattern_a(**kwargs))
        written.append(str(p))
    elif pattern == "B":
        scripts = render_pattern_b(**kwargs)
        for name, key in [("stageB_transfer.sh", "transfer"), ("stageB_train.sh", "train"), ("stageB_submit.sh", "submit")]:
            p = out / name
            _write(p, scripts[key])
            written.append(str(p))
    elif pattern == "C":
        scripts = render_pattern_c(**kwargs)
        for name, key in [("stageC.sh", "job"), ("lru_evict.sh", "lru")]:
            p = out / name
            _write(p, scripts[key])
            written.append(str(p))
    else:
        raise ValueError(f"未知のパターン: {pattern!r}(A/B/Cのいずれか)")

    return written
