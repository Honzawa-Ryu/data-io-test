"""シード固定の合成画像生成ヘルパ。全フォーマットで同一内容になるよう共通化する。"""

from __future__ import annotations

import numpy as np
from PIL import Image


def make_random_array(rng: np.random.Generator, height: int, width: int) -> np.ndarray:
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def make_random_image(rng: np.random.Generator, height: int, width: int) -> Image.Image:
    return Image.fromarray(make_random_array(rng, height, width), mode="RGB")


def encode_image(img: Image.Image, fmt: str) -> bytes:
    import io

    buf = io.BytesIO()
    pil_fmt = "JPEG" if fmt.lower() in ("jpg", "jpeg") else fmt.upper()
    img.save(buf, format=pil_fmt)
    return buf.getvalue()
