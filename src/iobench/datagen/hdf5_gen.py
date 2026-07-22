"""HDF5形式の合成データセット生成。チャンクサイズ指定可(64KB〜16MB)。"""

from __future__ import annotations

import time
from pathlib import Path

import h5py
import numpy as np

from iobench.datagen.synth import make_random_array


def generate_hdf5(
    out_path: str,
    num_images: int,
    chunk_size_bytes: int = 1024 * 1024,
    height: int = 512,
    width: int = 512,
    seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)
    bytes_per_image = height * width * 3
    chunk_images = max(1, min(num_images, chunk_size_bytes // bytes_per_image))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    with h5py.File(out_path, "w") as f:
        dset = f.create_dataset(
            "images",
            shape=(num_images, height, width, 3),
            dtype="uint8",
            chunks=(chunk_images, height, width, 3),
        )
        for i in range(num_images):
            dset[i] = make_random_array(rng, height, width)
    elapsed = time.perf_counter() - t0

    return {
        "format": "hdf5",
        "num_files": num_images,
        "chunk_images": chunk_images,
        "chunk_size_bytes": chunk_size_bytes,
        "total_bytes": Path(out_path).stat().st_size,
        "generation_seconds": elapsed,
        "seed": seed,
    }
