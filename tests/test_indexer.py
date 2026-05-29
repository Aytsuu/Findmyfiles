from __future__ import annotations

from pathlib import Path

from findmyfiles.config import IndexerConfig
from findmyfiles.indexer import Indexer
from findmyfiles.store import VectorStore


def test_indexer_chunks_text_and_skips_unchanged_files(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("one two three four five six seven eight", encoding="utf-8")

    store = VectorStore(tmp_path / "store")
    indexer = Indexer(
        store,
        IndexerConfig(batch_size=5, chunk_tokens=3, chunk_overlap=1, model="test"),
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
    indexer = Indexer(store, IndexerConfig())

    indexer.index_file(file_path)
    assert indexer.remove_file(file_path) >= 1
    assert store.stats()["chunks"] == 0
