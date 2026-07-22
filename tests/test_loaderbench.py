import pytest

torch = pytest.importorskip("torch")

from iobench.datagen import generate_hdf5, generate_raw, generate_webdataset, generate_zarr_pair
from iobench.loaderbench import run_loader_epoch


def test_raw_loader_reads_all_samples(tmp_path):
    generate_raw(str(tmp_path / "raw"), num_images=20, files_per_dir=5, height=16, width=16, seed=0)
    result = run_loader_epoch("raw", str(tmp_path / "raw"), decode=True, num_workers=0, batch_size=4)
    assert result.num_samples == 20
    assert result.throughput_samples_s > 0
    assert result.first_batch_latency_s >= 0


def test_webdataset_loader_reads_all_samples(tmp_path):
    generate_webdataset(str(tmp_path / "wds"), num_images=20, shard_size_bytes=4000, height=16, width=16, seed=0)
    result = run_loader_epoch(
        "webdataset", str(tmp_path / "wds"), decode=True, shuffle_mode="shard", num_workers=0, batch_size=4
    )
    assert result.num_samples == 20


def test_hdf5_loader_reads_all_samples(tmp_path):
    generate_hdf5(str(tmp_path / "imgs.h5"), num_images=20, chunk_size_bytes=4096, height=16, width=16, seed=0)
    result = run_loader_epoch("hdf5", str(tmp_path / "imgs.h5"), decode=True, num_workers=0, batch_size=4)
    assert result.num_samples == 20


def test_zarr_v3_loader_reads_all_samples(tmp_path):
    generate_zarr_pair(str(tmp_path / "z"), num_images=20, chunk_size_bytes=4096, height=16, width=16, seed=0)
    result = run_loader_epoch("zarr_v3", str(tmp_path / "z" / "v3.zarr"), decode=True, num_workers=0, batch_size=4)
    assert result.num_samples == 20


def test_decode_false_still_counts_samples(tmp_path):
    generate_raw(str(tmp_path / "raw"), num_images=12, files_per_dir=4, height=16, width=16, seed=0)
    result = run_loader_epoch("raw", str(tmp_path / "raw"), decode=False, num_workers=0, batch_size=4)
    assert result.num_samples == 12
    # decode=Falseでもバイト数合計が積算される
    assert result.total_bytes > 0


@pytest.mark.parametrize("shuffle_mode", ["none", "shard", "full"])
def test_map_style_all_shuffle_modes_read_all_samples(tmp_path, shuffle_mode):
    generate_raw(str(tmp_path / "raw"), num_images=30, files_per_dir=10, height=16, width=16, seed=0)
    result = run_loader_epoch(
        "raw", str(tmp_path / "raw"), decode=True, shuffle_mode=shuffle_mode, num_workers=0, batch_size=4
    )
    assert result.num_samples == 30


def test_webdataset_none_and_shard_both_read_all(tmp_path):
    generate_webdataset(str(tmp_path / "wds"), num_images=20, shard_size_bytes=2000, height=16, width=16, seed=0)
    for mode in ("none", "shard"):
        result = run_loader_epoch(
            "webdataset", str(tmp_path / "wds"), decode=True, shuffle_mode=mode, num_workers=0, batch_size=4
        )
        assert result.num_samples == 20


def test_webdataset_full_is_rejected(tmp_path):
    from iobench.loaderbench.shuffle import WebdatasetFullShuffleUnsupported

    generate_webdataset(str(tmp_path / "wds"), num_images=20, shard_size_bytes=2000, height=16, width=16, seed=0)
    with pytest.raises(WebdatasetFullShuffleUnsupported):
        run_loader_epoch(
            "webdataset", str(tmp_path / "wds"), decode=True, shuffle_mode="full", num_workers=0, batch_size=4
        )
