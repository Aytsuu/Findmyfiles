from __future__ import annotations

from pathlib import Path


def extract_video_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()
