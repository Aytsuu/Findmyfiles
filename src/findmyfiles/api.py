from __future__ import annotations

from dataclasses import asdict
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from findmyfiles.config import AppConfig
from findmyfiles.indexer import Indexer
from findmyfiles.runtime import ScanStatus
from findmyfiles.store import VectorStore


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    n_results: int = Field(default=10, ge=1, le=50)
    filters: dict[str, Any] | None = None


class IndexRequest(BaseModel):
    path: str = Field(min_length=1)


def create_app(
    *,
    config: AppConfig,
    store: VectorStore,
    indexer: Indexer,
    scan_status: ScanStatus | None = None,
) -> FastAPI:
    app = FastAPI(title="findmyfiles")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "stats": store.stats(),
            "indexing": None if scan_status is None else scan_status.snapshot().__dict__,
        }

    @app.get("/config")
    def get_config() -> dict[str, Any]:
        payload = asdict(config)
        payload["watcher"]["roots"] = [str(root) for root in config.watcher.roots]
        payload["storage"]["chroma_dir"] = str(config.storage.chroma_dir)
        return payload

    @app.post("/search")
    def search(request: SearchRequest) -> dict[str, Any]:
        start = perf_counter()
        query_embedding = indexer.embed_query(request.query)
        results = store.query(
            query_embedding,
            n_results=request.n_results,
            filters=request.filters,
        )
        return {
            "results": results,
            "query_time_ms": round((perf_counter() - start) * 1000, 3),
        }

    @app.post("/index")
    def index_path(request: IndexRequest) -> dict[str, Any]:
        indexed = indexer.index_file(request.path)
        if indexed is None:
            raise HTTPException(status_code=404, detail="path not found")
        return {
            "indexed": str(indexed.path),
            "chunks": len(indexed.chunks),
        }

    @app.delete("/index")
    def delete_index(request: IndexRequest) -> dict[str, Any]:
        deleted = indexer.remove_file(request.path)
        return {"deleted": deleted}

    return app
