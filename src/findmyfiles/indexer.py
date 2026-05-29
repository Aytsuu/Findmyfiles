from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import mimetypes

from findmyfiles.config import IndexerConfig
from findmyfiles.embeddings import Embedder, GeminiEmbedder, GeminiEmbeddingConfig
from findmyfiles.extractors.image import load_image
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


class Indexer:
    TEXT_SUFFIXES = frozenset({".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml"})
    IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"})
    SUPPORTED_SUFFIXES = frozenset({*TEXT_SUFFIXES, ".pdf", ".docx", ".xlsx", *IMAGE_SUFFIXES})

    def __init__(
        self,
        store: VectorStore,
        config: IndexerConfig,
        *,
        embedder: Embedder | None = None,
        gemini_api_key: str | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.embedder = embedder or GeminiEmbedder(
            GeminiEmbeddingConfig(
                api_key=gemini_api_key or "",
                model=config.model,
            )
        )

    def index_file(self, path: str | Path) -> IndexedFile | None:
        target = Path(path)
        if not target.is_file():
            return None

        suffix = target.suffix.lower()
        if not self._is_supported_suffix(suffix):
            stat = target.stat()
            self.store.delete(target)
            return IndexedFile(
                path=target.resolve(),
                mime=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                size=stat.st_size,
                mtime=stat.st_mtime,
                chunks=[],
            )

        stat = target.stat()
        if not self.store.is_stale(target, mtime=stat.st_mtime, size=stat.st_size):
            return None

        extracted = self._extract(target)
        if not extracted.chunks:
            self.store.delete(target)
            return extracted

        if suffix in self.IMAGE_SUFFIXES:
            embeddings = self.embedder.embed_images([load_image(target)])
        else:
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

    def _is_supported_suffix(self, suffix: str) -> bool:
        return suffix in self.SUPPORTED_SUFFIXES

    def _extract(self, path: Path) -> IndexedFile:
        suffix = path.suffix.lower()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        if suffix in self.TEXT_SUFFIXES:
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
        elif suffix in self.IMAGE_SUFFIXES:
            chunks = [path.name]
        else:
            chunks = []

        stat = path.stat()
        return IndexedFile(
            path=path.resolve(),
            mime=mime,
            size=stat.st_size,
            mtime=stat.st_mtime,
            chunks=chunks,
        )
