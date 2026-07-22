"""WebDataset tarシャード形式の合成データセット生成。シャードサイズ指定可(10MB〜5GB)。"""

from __future__ import annotations

import io
import tarfile
import time
from pathlib import Path

import numpy as np

from iobench.datagen.synth import encode_image, make_random_image


def generate_webdataset(
    out_dir: str,
    num_images: int,
    shard_size_bytes: int = 512 * 1024 * 1024,
    height: int = 512,
    width: int = 512,
    fmt: str = "jpg",
    seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    shard_idx = 0
    current_size = 0
    tar: tarfile.TarFile | None = None
    total_bytes = 0

    t0 = time.perf_counter()
    for i in range(num_images):
        if tar is None or current_size >= shard_size_bytes:
            if tar is not None:
                tar.close()
            shard_path = root / f"shard-{shard_idx:06d}.tar"
            tar = tarfile.open(shard_path, "w")
            shard_idx += 1
            current_size = 0

        img = make_random_image(rng, height, width)
        data = encode_image(img, fmt)
        info = tarfile.TarInfo(name=f"{i:07d}.{fmt}")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        current_size += len(data)
        total_bytes += len(data)

    if tar is not None:
        tar.close()
    elapsed = time.perf_counter() - t0

    return {
        "format": "webdataset",
        "num_files": num_images,
        "num_shards": shard_idx,
        "shard_size_bytes": shard_size_bytes,
        "total_bytes": total_bytes,
        "generation_seconds": elapsed,
        "seed": seed,
    }
