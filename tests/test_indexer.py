from __future__ import annotations

from pathlib import Path

from PIL import Image

from findmyfiles.config import IndexerConfig
from findmyfiles.embeddings import Embedder
from findmyfiles.indexer import Indexer
from findmyfiles.store import VectorStore


class FakeEmbedder(Embedder):
    def embed_documents(self, chunks: list[str]) -> list[tuple[float, ...]]:
        return [self._embed(chunk) for chunk in chunks]

    def embed_images(self, images: list[Image.Image]) -> list[tuple[float, ...]]:
        return [(float(image.size[0]), float(image.size[1])) for image in images]

    def embed_query(self, query: str) -> tuple[float, ...]:
        return self._embed(query)

    def _embed(self, value: str) -> tuple[float, ...]:
        return (float(len(value)), float(sum(ord(char) for char in value) % 97))


def test_indexer_chunks_text_and_skips_unchanged_files(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("one two three four five six seven eight", encoding="utf-8")

    store = VectorStore(tmp_path / "store")
    indexer = Indexer(
        store,
        IndexerConfig(batch_size=5, chunk_tokens=3, chunk_overlap=1, model="test"),
        embedder=FakeEmbedder(),
    )

    indexed = indexer.index_file(file_path)
    assert indexed is not None
    assert indexed.chunks == ["one two three", "three four five", "five six seven", "seven eight"]
    assert store.stats() == {"documents": 1, "chunks": 4}

    skipped = indexer.index_file(file_path)
    assert skipped is None


def test_indexer_remove_file(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha beta gamma", encoding="utf-8")
    store = VectorStore(tmp_path / "store")
    indexer = Indexer(store, IndexerConfig(), embedder=FakeEmbedder())

    indexer.index_file(file_path)
    assert indexer.remove_file(file_path) >= 1
    assert store.stats()["chunks"] == 0


def test_indexer_indexes_images(tmp_path: Path) -> None:
    file_path = tmp_path / "photo.jpg"
    Image.new("RGB", (12, 8), color="red").save(file_path)

    store = VectorStore(tmp_path / "store")
    indexer = Indexer(store, IndexerConfig(), embedder=FakeEmbedder())

    indexed = indexer.index_file(file_path)

    assert indexed is not None
    assert indexed.chunks == ["photo.jpg"]
    assert store.stats() == {"documents": 1, "chunks": 1}


def test_indexer_removes_existing_unsupported_records(tmp_path: Path) -> None:
    file_path = tmp_path / "archive.bin"
    file_path.write_bytes(b"fake-bin")

    store = VectorStore(tmp_path / "store")
    store.upsert(
        file_path,
        ["archive.bin"],
        [(1.0, 0.0)],
        mime="application/octet-stream",
        mtime=1.0,
        size=8,
    )

    indexer = Indexer(store, IndexerConfig(), embedder=FakeEmbedder())
    indexed = indexer.index_file(file_path)

    assert indexed is not None
    assert indexed.chunks == []
    assert store.stats() == {"documents": 0, "chunks": 0}
