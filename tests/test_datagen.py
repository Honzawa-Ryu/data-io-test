from pathlib import Path

from iobench.datagen.hdf5_gen import generate_hdf5
from iobench.datagen.raw import generate_raw
from iobench.datagen.webdataset_gen import generate_webdataset
from iobench.datagen.zarr_gen import generate_zarr, generate_zarr_pair


def test_generate_raw_creates_expected_file_count(tmp_path):
    meta = generate_raw(str(tmp_path / "raw"), num_images=17, files_per_dir=5, height=8, width=8, seed=1)
    files = list(Path(tmp_path / "raw").rglob("*.jpg"))
    assert len(files) == 17
    assert meta["num_files"] == 17


def test_generate_raw_is_seed_reproducible(tmp_path):
    generate_raw(str(tmp_path / "a"), num_images=3, files_per_dir=10, height=8, width=8, seed=42)
    generate_raw(str(tmp_path / "b"), num_images=3, files_per_dir=10, height=8, width=8, seed=42)
    a_bytes = (tmp_path / "a" / "shard_00000" / "img_0000000.jpg").read_bytes()
    b_bytes = (tmp_path / "b" / "shard_00000" / "img_0000000.jpg").read_bytes()
    assert a_bytes == b_bytes


def test_generate_webdataset_respects_shard_size(tmp_path):
    meta = generate_webdataset(
        str(tmp_path / "wds"), num_images=10, shard_size_bytes=500, height=8, width=8, seed=0
    )
    shards = list((tmp_path / "wds").glob("*.tar"))
    assert len(shards) == meta["num_shards"]
    assert meta["num_shards"] >= 1


def test_generate_hdf5_shape(tmp_path):
    h5py = __import__("h5py")
    out = tmp_path / "imgs.h5"
    generate_hdf5(str(out), num_images=5, chunk_size_bytes=1024, height=8, width=8, seed=0)
    with h5py.File(out, "r") as f:
        assert f["images"].shape == (5, 8, 8, 3)


def test_generate_zarr_v3_shape(tmp_path):
    zarr = __import__("zarr")
    out = tmp_path / "imgs.zarr"
    generate_zarr(str(out), num_images=5, chunk_size_bytes=1024, height=8, width=8, seed=0, zarr_format=3)
    arr = zarr.open(str(out), mode="r")
    assert arr.shape == (5, 8, 8, 3)


def test_generate_zarr_pair_creates_v3_and_v2(tmp_path):
    zarr = __import__("zarr")
    out = tmp_path / "z"
    meta = generate_zarr_pair(str(out), num_images=6, chunk_size_bytes=1024, height=8, width=8, seed=7)
    assert (out / "v3.zarr").exists()
    assert (out / "v2_reference.zarr").exists()
    assert meta["zarr_v3"]["format"] == "zarr_v3"
    assert meta["zarr_v2"]["format"] == "zarr_v2"
    # 同一seedなのでv3とv2の内容は一致する
    v3 = zarr.open(str(out / "v3.zarr"), mode="r")
    v2 = zarr.open(str(out / "v2_reference.zarr"), mode="r")
    assert (v3[:] == v2[:]).all()
