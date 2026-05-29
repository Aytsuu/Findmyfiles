from __future__ import annotations

from pathlib import Path

from PIL import Image


def load_image(path: str | Path) -> Image.Image:
    with Image.open(Path(path)) as image:
        return image.copy()
