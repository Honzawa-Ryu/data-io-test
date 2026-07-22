"""Zarr形式の合成データセット生成。Zarr v3 sharded(既定)+ 参考用Zarr v2。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import numpy as np
import zarr

from iobench.datagen.synth import make_random_array


def generate_zarr(
    out_path: str,
    num_images: int,
    chunk_size_bytes: int = 1024 * 1024,
    height: int = 512,
    width: int = 512,
    seed: int = 0,
    zarr_format: int = 3,
    shard_images: int | None = None,
) -> dict:
    """zarr_format=3 の場合、shard_images(既定: chunk_imagesの8倍)単位でshardingする。
    zarr_format=2 は参考用で shards は使わない。
    """
    rng = np.random.default_rng(seed)
    bytes_per_image = height * width * 3
    chunk_images = max(1, min(num_images, chunk_size_bytes // bytes_per_image))

    out = Path(out_path)
    if out.exists():
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {}
    if zarr_format == 3:
        # Zarr v3のshardは内側chunkの整数倍でなければならない(末尾の部分shardは許容される)。
        # 指定値をchunk_imagesの倍数へ丸め、配列サイズも超えないようにする。
        target = shard_images or chunk_images * 8
        shard_n = max(chunk_images, (target // chunk_images) * chunk_images)
        shard_n = min(shard_n, ((num_images + chunk_images - 1) // chunk_images) * chunk_images)
        kwargs["shards"] = (shard_n, height, width, 3)

    t0 = time.perf_counter()
    arr = zarr.create_array(
        store=str(out),
        shape=(num_images, height, width, 3),
        chunks=(chunk_images, height, width, 3),
        dtype="uint8",
        zarr_format=zarr_format,
        overwrite=True,
        **kwargs,
    )
    for i in range(num_images):
        arr[i] = make_random_array(rng, height, width)
    elapsed = time.perf_counter() - t0

    total_bytes = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())

    return {
        "format": f"zarr_v{zarr_format}",
        "num_files": num_images,
        "chunk_images": chunk_images,
        "chunk_size_bytes": chunk_size_bytes,
        "total_bytes": total_bytes,
        "generation_seconds": elapsed,
        "seed": seed,
    }


def generate_zarr_pair(
    out_dir: str,
    num_images: int,
    chunk_size_bytes: int = 1024 * 1024,
    height: int = 512,
    width: int = 512,
    seed: int = 0,
    shard_images: int | None = None,
) -> dict:
    """goal.md 2.5: 「Zarr v3 sharded(同チャンク掃引)+ 参考用 Zarr v2」を同一内容・同一seedで
    同時生成する。v3が主系列、v2はチャンク/シャード効果を比較するための参考コピー。
    loaderbench の Condition.format ではどちらを読んだかを zarr_v3/zarr_v2 で区別する。
    """
    v3_meta = generate_zarr(
        str(Path(out_dir) / "v3.zarr"),
        num_images,
        chunk_size_bytes=chunk_size_bytes,
        height=height,
        width=width,
        seed=seed,
        zarr_format=3,
        shard_images=shard_images,
    )
    v2_meta = generate_zarr(
        str(Path(out_dir) / "v2_reference.zarr"),
        num_images,
        chunk_size_bytes=chunk_size_bytes,
        height=height,
        width=width,
        seed=seed,
        zarr_format=2,
    )
    return {"format": "zarr", "zarr_v3": v3_meta, "zarr_v2": v2_meta}
