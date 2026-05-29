from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import mimetypes

from findmyfiles.config import IndexerConfig
from findmyfiles.extractors.office import extract_docx_text, extract_xlsx_text
from findmyfiles.extractors.pdf import extract_pdf_text
from findmyfiles.extractors.text import chunk_text, extract_text
from findmyfiles.store import VectorStore


@dataclass(frozen=True)
class IndexedFile:
    path: Path
    mime: str
    size: int
    mtime: float
    chunks: list[str]


class DeterministicEmbedder:
    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = dimensions

    def embed_documents(self, chunks: list[str]) -> list[tuple[float, ...]]:
        return [self._embed(chunk) for chunk in chunks]

    def embed_query(self, query: str) -> tuple[float, ...]:
        return self._embed(query)

    def _embed(self, value: str) -> tuple[float, ...]:
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        values = []
        for index in range(self.dimensions):
            byte = digest[index]
            values.append((byte / 255.0) * 2.0 - 1.0)
        return tuple(values)


class Indexer:
    def __init__(
        self,
        store: VectorStore,
        config: IndexerConfig,
        *,
        embedder: DeterministicEmbedder | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.embedder = embedder or DeterministicEmbedder()

    def index_file(self, path: str | Path) -> IndexedFile | None:
        target = Path(path)
        if not target.is_file():
            return None

        stat = target.stat()
        if not self.store.is_stale(target, mtime=stat.st_mtime, size=stat.st_size):
            return None

        extracted = self._extract(target)
        if not extracted.chunks:
            self.store.delete(target)
            return extracted

        embeddings = self.embedder.embed_documents(extracted.chunks)
        self.store.upsert(
            target,
            extracted.chunks,
            embeddings,
            mime=extracted.mime,
            mtime=extracted.mtime,
            size=extracted.size,
        )
        return extracted

    def remove_file(self, path: str | Path) -> int:
        return self.store.delete(path)

    def embed_query(self, query: str) -> tuple[float, ...]:
        return self.embedder.embed_query(query)

    def _extract(self, path: Path) -> IndexedFile:
        suffix = path.suffix.lower()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        if suffix in {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml"}:
            text = extract_text(path)
            chunks = chunk_text(
                text,
                chunk_tokens=self.config.chunk_tokens,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif suffix == ".pdf":
            text = extract_pdf_text(path)
            chunks = chunk_text(
                text,
                chunk_tokens=self.config.chunk_tokens,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif suffix == ".docx":
            text = extract_docx_text(path)
            chunks = chunk_text(
                text,
                chunk_tokens=self.config.chunk_tokens,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif suffix == ".xlsx":
            text = extract_xlsx_text(path)
            chunks = chunk_text(
                text,
                chunk_tokens=self.config.chunk_tokens,
                chunk_overlap=self.config.chunk_overlap,
            )
        else:
            chunks = [path.name]

        stat = path.stat()
        return IndexedFile(
            path=path.resolve(),
            mime=mime,
            size=stat.st_size,
            mtime=stat.st_mtime,
            chunks=chunks,
        )
