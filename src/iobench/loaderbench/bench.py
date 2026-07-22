"""DataLoaderで1エポック読み切り、実効スループット・first-batch latency・GPU待ちを計測する。"""

from __future__ import annotations

import time
from dataclasses import dataclass

import torch
from torch.utils.data import DataLoader, IterableDataset

from iobench.loaderbench.datasets import (
    Hdf5Dataset,
    RawFileDataset,
    WebDatasetShards,
    ZarrDataset,
)


@dataclass
class LoaderResult:
    num_samples: int
    total_bytes: int
    elapsed_seconds: float
    first_batch_latency_s: float
    throughput_samples_s: float
    throughput_mb_s: float
    gpu_idle_ratio: float | None


def _build_dataset(
    fmt: str,
    path: str,
    decode: bool,
    shuffle_mode: str,
    seed: int,
):
    if fmt == "raw":
        return RawFileDataset(path, decode=decode)
    if fmt == "webdataset":
        return WebDatasetShards(path, decode=decode, shuffle_mode=shuffle_mode, seed=seed)
    if fmt == "hdf5":
        return Hdf5Dataset(path, decode=decode)
    if fmt in ("zarr_v3", "zarr_v2"):
        return ZarrDataset(path, decode=decode)
    raise ValueError(f"未知のフォーマット: {fmt!r}")


def _collate(batch):
    # decode=Falseのときは要素がintバイト数、Trueのときはテンソル
    if isinstance(batch[0], torch.Tensor):
        return torch.stack(batch)
    return torch.tensor(batch)


def run_loader_epoch(
    fmt: str,
    path: str,
    *,
    decode: bool = True,
    shuffle_mode: str = "none",
    num_workers: int = 0,
    batch_size: int = 32,
    seed: int = 0,
    to_gpu: bool = False,
    bytes_per_sample_hint: int | None = None,
    shuffle_block_size: int = 64,
) -> LoaderResult:
    dataset = _build_dataset(fmt, path, decode, shuffle_mode, seed)
    is_iterable = isinstance(dataset, IterableDataset)

    # map系Datasetは none/shard/full をSamplerで実現する(webdataset側はDataset内で処理)。
    sampler = None
    if not is_iterable:
        from iobench.loaderbench.shuffle import make_map_sampler

        sampler = make_map_sampler(len(dataset), shuffle_mode, seed, shuffle_block_size)

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        sampler=sampler,
        collate_fn=_collate,
        drop_last=False,
    )

    device = torch.device("cuda") if (to_gpu and torch.cuda.is_available()) else None
    num_samples = 0
    total_bytes = 0
    gpu_wait_accum = 0.0

    t_start = time.perf_counter()
    first_batch_latency = None
    prev_batch_end = t_start

    for batch in loader:
        now = time.perf_counter()
        if first_batch_latency is None:
            first_batch_latency = now - t_start
        # 前バッチ処理終了から次バッチ取得までの待ち = データ供給待ち(GPU idle相当)
        gpu_wait_accum += now - prev_batch_end

        if isinstance(batch, torch.Tensor) and batch.dtype == torch.uint8:
            n = batch.shape[0]
            total_bytes += int(batch.numel())
        else:
            n = int(batch.shape[0])
            total_bytes += int(batch.sum().item())

        num_samples += n
        if device is not None and isinstance(batch, torch.Tensor) and batch.is_floating_point() is False and batch.dtype == torch.uint8:
            batch.to(device, non_blocking=True)
        prev_batch_end = time.perf_counter()

    elapsed = time.perf_counter() - t_start

    if bytes_per_sample_hint is not None and total_bytes == 0:
        total_bytes = bytes_per_sample_hint * num_samples

    throughput_samples = num_samples / elapsed if elapsed > 0 else 0.0
    throughput_mb = (total_bytes / (1024**2)) / elapsed if elapsed > 0 else 0.0
    gpu_idle_ratio = (gpu_wait_accum / elapsed) if (to_gpu and elapsed > 0) else None

    return LoaderResult(
        num_samples=num_samples,
        total_bytes=total_bytes,
        elapsed_seconds=elapsed,
        first_batch_latency_s=first_batch_latency or 0.0,
        throughput_samples_s=throughput_samples,
        throughput_mb_s=throughput_mb,
        gpu_idle_ratio=gpu_idle_ratio,
    )
