"""生ファイル形式の合成データセット生成。ディレクトリあたりファイル数を変数化する。"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from iobench.datagen.synth import encode_image, make_random_image


def generate_raw(
    out_dir: str,
    num_images: int,
    files_per_dir: int = 1000,
    height: int = 512,
    width: int = 512,
    fmt: str = "jpg",
    seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    t0 = time.perf_counter()
    for i in range(num_images):
        subdir = root / f"shard_{i // files_per_dir:05d}"
        subdir.mkdir(exist_ok=True)
        img = make_random_image(rng, height, width)
        data = encode_image(img, fmt)
        path = subdir / f"img_{i:07d}.{fmt}"
        path.write_bytes(data)
        total_bytes += len(data)
    elapsed = time.perf_counter() - t0

    return {
        "format": "raw",
        "num_files": num_images,
        "files_per_dir": files_per_dir,
        "total_bytes": total_bytes,
        "generation_seconds": elapsed,
        "seed": seed,
    }
