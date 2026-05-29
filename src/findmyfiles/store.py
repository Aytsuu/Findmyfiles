from __future__ import annotations

from hashlib import sha256
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger("findmyfiles.store")


def _import_chromadb() -> Any:
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - exercised in runtime only
        msg = "chromadb is required at runtime. Install dependencies with `python -m pip install -e .`."
        raise RuntimeError(msg) from exc
    return chromadb


def _build_where(filters: dict[str, Any]) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []

    mime = filters.get("mime")
    if mime:
        clauses.append({"mime": mime})

    mtime_from = filters.get("mtime_from")
    if mtime_from is not None:
        clauses.append({"mtime": {"$gte": float(mtime_from)}})

    mtime_to = filters.get("mtime_to")
    if mtime_to is not None:
        clauses.append({"mtime": {"$lte": float(mtime_to)}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class VectorStore:
    def __init__(self, root: str | Path, *, collection_name: str = "findmyfiles") -> None:
        chromadb = _import_chromadb()
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.root))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        file_path: str | Path,
        chunks: list[str],
        embeddings: list[tuple[float, ...]],
        *,
        mime: str,
        mtime: float,
        size: int,
    ) -> None:
        normalized_path = str(Path(file_path).resolve())
        self.delete(normalized_path)
        if not chunks:
            return

        ids = [_record_id(normalized_path, chunk_index) for chunk_index in range(len(chunks))]
        metadatas = [
            {
                "path": normalized_path,
                "mtime": float(mtime),
                "chunk": chunk_index,
                "mime": mime,
                "size": int(size),
            }
            for chunk_index in range(len(chunks))
        ]
        for record_id, metadata, embedding in zip(ids, metadatas, embeddings, strict=True):
            logger.info(
                "chroma upsert pending id=%s path=%s chunk=%s dims=%s mime=%s size=%s",
                record_id,
                metadata["path"],
                metadata["chunk"],
                len(embedding),
                metadata["mime"],
                metadata["size"],
            )
        self._collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=[list(embedding) for embedding in embeddings],
            metadatas=metadatas,
        )
        logger.info(
            "chroma upsert complete path=%s chunks=%s",
            normalized_path,
            len(chunks),
        )

    def delete(self, file_path: str | Path) -> int:
        normalized_path = str(Path(file_path).resolve())
        existing = self._collection.get(where={"path": normalized_path}, include=[])
        ids = list(existing.get("ids", []))
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def is_stale(self, file_path: str | Path, *, mtime: float, size: int) -> bool:
        normalized_path = str(Path(file_path).resolve())
        existing = self._collection.get(
            where={"path": normalized_path},
            limit=1,
            include=["metadatas"],
        )
        metadatas = existing.get("metadatas") or []
        if not metadatas:
            return True
        current = metadatas[0] or {}
        current_mtime = float(current.get("mtime", -1.0))
        current_size = int(current.get("size", -1))
        return (not math.isclose(current_mtime, float(mtime), rel_tol=0.0, abs_tol=1e-6)) or current_size != int(size)

    def query(
        self,
        embedding: tuple[float, ...],
        *,
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        active_filters = filters or {}
        where = _build_where(active_filters)
        candidate_ids = self._candidate_ids(active_filters, where)
        if candidate_ids == []:
            return []

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [list(embedding)],
            "n_results": max(n_results, 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            query_kwargs["where"] = where
        if candidate_ids is not None:
            query_kwargs["ids"] = candidate_ids

        raw = self._collection.query(**query_kwargs)
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[dict[str, Any]] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=True):
            if metadata is None:
                continue
            if not _matches_post_filters(metadata, active_filters):
                continue
            results.append(
                {
                    "path": metadata["path"],
                    "score": _distance_to_score(float(distance)),
                    "chunk": int(metadata["chunk"]),
                    "snippet": str(document)[:240],
                    "mime": metadata["mime"],
                    "size": int(metadata["size"]),
                    "mtime": float(metadata["mtime"]),
                }
            )
            if len(results) >= n_results:
                break

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:n_results]

    def stats(self) -> dict[str, int]:
        chunk_count = int(self._collection.count())
        if chunk_count == 0:
            return {"documents": 0, "chunks": 0}

        rows = self._collection.get(limit=chunk_count, include=["metadatas"])
        metadatas = rows.get("metadatas") or []
        unique_paths = {metadata["path"] for metadata in metadatas if metadata is not None}
        return {
            "documents": len(unique_paths),
            "chunks": chunk_count,
        }

    def _candidate_ids(
        self,
        filters: dict[str, Any],
        where: dict[str, Any] | None,
    ) -> list[str] | None:
        path_prefix = filters.get("path_prefix")
        if not path_prefix:
            return None

        normalized_prefix = str(Path(path_prefix).resolve())
        chunk_count = int(self._collection.count())
        if chunk_count == 0:
            return []

        rows = self._collection.get(limit=chunk_count, include=["metadatas"], where=where)
        ids = rows.get("ids") or []
        metadatas = rows.get("metadatas") or []
        return [
            record_id
            for record_id, metadata in zip(ids, metadatas, strict=True)
            if metadata is not None and str(metadata.get("path", "")).startswith(normalized_prefix)
        ]


def _distance_to_score(distance: float) -> float:
    return 1.0 / (1.0 + max(distance, 0.0))


def _matches_post_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    path_prefix = filters.get("path_prefix")
    if path_prefix and not str(metadata.get("path", "")).startswith(str(Path(path_prefix).resolve())):
        return False
    return True


def _record_id(normalized_path: str, chunk_index: int) -> str:
    return sha256(f"{normalized_path}::{chunk_index}".encode("utf-8")).hexdigest()
