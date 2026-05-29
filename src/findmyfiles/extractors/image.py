from __future__ import annotations

from pathlib import Path


def load_image_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()
