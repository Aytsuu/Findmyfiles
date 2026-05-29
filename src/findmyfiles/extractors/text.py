from __future__ import annotations

from pathlib import Path


def extract_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, *, chunk_tokens: int, chunk_overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_tokens - chunk_overlap)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        end = start + chunk_tokens
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
    return chunks
