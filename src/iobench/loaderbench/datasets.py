"""各フォーマットのPyTorch Datasetラッパ。decode {あり/なし} を切り替えられるようにする。

decode=True: 画像をデコードしてテンソル化(実効的なデータ供給性能)
decode=False: バイト列を読むだけ(ストレージ帯域の上限。デコードCPUコストを除外)
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset, IterableDataset


def _decode_bytes(data: bytes) -> torch.Tensor:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return torch.from_numpy(np.array(img)).permute(2, 0, 1).contiguous()


class RawFileDataset(Dataset):
    def __init__(self, root: str, decode: bool = True) -> None:
        self.paths = sorted(Path(root).rglob("*.jpg")) + sorted(Path(root).rglob("*.png"))
        if not self.paths:
            raise FileNotFoundError(
                f"raw データセットが空です: {root} 配下に *.jpg/*.png がありません。\n"
                "--dataset-root と実験定義の format の対応を確認してください。"
            )
        self.decode = decode

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int):
        data = self.paths[idx].read_bytes()
        if self.decode:
            return _decode_bytes(data)
        return len(data)


class WebDatasetShards(IterableDataset):
    """tarシャードを読むiterable実装。shuffle_modeで挙動が変わる:

    - none : シャード順そのまま、シャード内順そのまま
    - shard: シャード順シャッフル + シャッフルバッファ(シャード内サンプル並べ替え)
    - full : tar逐次構造では真の完全ランダムを実現できないため未対応(展開時にスキップ)
    """

    def __init__(
        self,
        root: str,
        decode: bool = True,
        shuffle_mode: str = "none",
        seed: int = 0,
        shuffle_buffer: int = 256,
    ) -> None:
        from iobench.loaderbench.shuffle import WebdatasetFullShuffleUnsupported

        if shuffle_mode == "full":
            raise WebdatasetFullShuffleUnsupported(
                "webdataset は shuffle_mode='full'(完全ランダム)を実現できません。"
                "shard(シャード内シャッフル)を使うか、full を測るなら map系フォーマットを使ってください。"
            )
        self.shards = sorted(Path(root).glob("*.tar"))
        if not self.shards:
            raise FileNotFoundError(
                f"webdataset データセットが空です: {root} 直下に *.tar がありません。"
                "--dataset-root と実験定義の format の対応を確認してください。"
            )
        self.decode = decode
        self.shuffle_mode = shuffle_mode
        self.seed = seed
        self.shuffle_buffer = shuffle_buffer

    def _raw_stream(self, shards):
        for shard in shards:
            with tarfile.open(shard, "r") as tar:
                for member in tar:
                    if not member.isfile():
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    data = f.read()
                    yield _decode_bytes(data) if self.decode else len(data)

    def __iter__(self):
        shards = list(self.shards)
        if self.shuffle_mode == "shard":
            rng = np.random.default_rng(self.seed)
            rng.shuffle(shards)
        worker_info = torch.utils.data.get_worker_info()
        if worker_info is not None:
            shards = shards[worker_info.id :: worker_info.num_workers]

        stream = self._raw_stream(shards)
        if self.shuffle_mode == "shard":
            from iobench.loaderbench.shuffle import buffered_shuffle

            yield from buffered_shuffle(stream, self.shuffle_buffer, self.seed)
        else:
            yield from stream


class Hdf5Dataset(Dataset):
    def __init__(self, path: str, decode: bool = True) -> None:
        import h5py

        self.path = path
        self.decode = decode
        with h5py.File(path, "r") as f:
            self.length = f["images"].shape[0]
        self._file = None

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int):
        import h5py

        # worker毎にファイルハンドルを遅延オープン(fork安全)
        if self._file is None:
            self._file = h5py.File(self.path, "r")
        arr = self._file["images"][idx]
        if self.decode:
            return torch.from_numpy(arr).permute(2, 0, 1).contiguous()
        return int(arr.nbytes)


class ZarrDataset(Dataset):
    def __init__(self, path: str, decode: bool = True) -> None:
        import zarr

        self.path = path
        self.decode = decode
        self._arr = zarr.open(path, mode="r")
        self.length = self._arr.shape[0]

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int):
        arr = np.asarray(self._arr[idx])
        if self.decode:
            return torch.from_numpy(arr).permute(2, 0, 1).contiguous()
        return int(arr.nbytes)
