from __future__ import annotations

from pathlib import Path

from findmyfiles.store import VectorStore


def test_upsert_query_and_delete(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "store")
    file_path = tmp_path / "note.txt"
    file_path.write_text("alpha beta", encoding="utf-8")

    store.upsert(
        file_path,
        ["alpha beta", "gamma delta"],
        [(1.0, 0.0), (0.0, 1.0)],
        mime="text/plain",
        mtime=10.0,
        size=12,
    )

    results = store.query((1.0, 0.0), n_results=2)
    assert len(results) == 2
    assert results[0]["path"] == str(file_path.resolve())
    assert results[0]["score"] >= results[1]["score"]

    filtered = store.query((1.0, 0.0), filters={"mime": "application/pdf"})
    assert filtered == []

    deleted = store.delete(file_path)
    assert deleted == 2
    assert store.stats() == {"documents": 0, "chunks": 0}


def test_is_stale_uses_mtime_and_size(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "store")
    file_path = tmp_path / "note.txt"
    file_path.write_text("alpha", encoding="utf-8")

    assert store.is_stale(file_path, mtime=1.0, size=5) is True

    store.upsert(
        file_path,
        ["alpha"],
        [(1.0,)],
        mime="text/plain",
        mtime=1.0,
        size=5,
    )

    assert store.is_stale(file_path, mtime=1.0, size=5) is False
    assert store.is_stale(file_path, mtime=2.0, size=5) is True


def test_store_persists_through_chroma_reopen(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    store = VectorStore(store_root)
    file_path = tmp_path / "persist.txt"
    file_path.write_text("persist me", encoding="utf-8")

    store.upsert(
        file_path,
        ["persist me"],
        [(0.5, 0.25)],
        mime="text/plain",
        mtime=3.0,
        size=10,
    )

    reopened = VectorStore(store_root)
    results = reopened.query((0.5, 0.25), n_results=1)
    assert len(results) == 1
    assert results[0]["path"] == str(file_path.resolve())
