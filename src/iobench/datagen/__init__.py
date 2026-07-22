"""合成画像データセット生成(生ファイル/WebDataset/HDF5/Zarr)。シード固定で再現可能。"""

from iobench.datagen.hdf5_gen import generate_hdf5
from iobench.datagen.raw import generate_raw
from iobench.datagen.webdataset_gen import generate_webdataset
from iobench.datagen.zarr_gen import generate_zarr, generate_zarr_pair

__all__ = [
    "generate_raw",
    "generate_webdataset",
    "generate_hdf5",
    "generate_zarr",
    "generate_zarr_pair",
]
