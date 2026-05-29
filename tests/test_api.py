from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from findmyfiles.api import create_app
from findmyfiles.config import APIConfig, AppConfig, IndexerConfig, StorageConfig, WatcherConfig
from findmyfiles.indexer import Indexer
from findmyfiles.runtime import ScanStatus
from findmyfiles.store import VectorStore


def build_test_app(tmp_path: Path) -> TestClient:
    config = AppConfig(
        watcher=WatcherConfig(
            roots=(tmp_path,),
            exclude_globs=(),
            include_exts=(".txt",),
        ),
        indexer=IndexerConfig(),
        api=APIConfig(),
        storage=StorageConfig(chroma_dir=tmp_path / "store"),
        gemini_api_key=None,
    )
    store = VectorStore(config.storage.chroma_dir)
    indexer = Indexer(store, config.indexer)
    app = create_app(config=config, store=store, indexer=indexer, scan_status=ScanStatus())
    return TestClient(app)


def test_search_and_health_endpoints(tmp_path: Path) -> None:
    client = build_test_app(tmp_path)
    file_path = tmp_path / "doc.txt"
    file_path.write_text("project invoice march alpha beta", encoding="utf-8")

    index_response = client.post("/index", json={"path": str(file_path)})
    assert index_response.status_code == 200
    assert index_response.json()["chunks"] == 1

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["stats"]["documents"] == 1
    assert "indexing" in health_response.json()

    search_response = client.post("/search", json={"query": "invoice", "n_results": 5})
    assert search_response.status_code == 200
    payload = search_response.json()
    assert len(payload["results"]) == 1
    assert payload["results"][0]["path"] == str(file_path.resolve())
    assert "query_time_ms" in payload


def test_delete_index_endpoint(tmp_path: Path) -> None:
    client = build_test_app(tmp_path)
    file_path = tmp_path / "doc.txt"
    file_path.write_text("alpha beta", encoding="utf-8")
    client.post("/index", json={"path": str(file_path)})

    delete_response = client.request("DELETE", "/index", json={"path": str(file_path)})
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] >= 1
