from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
from typing import Any


@dataclass(frozen=True)
class StoreRecord:
    id: str
    document: str
    embedding: tuple[float, ...]
    metadata: dict[str, Any]


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


class VectorStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._records_path = self.root / "records.json"
        self._state_path = self.root / "file_state.json"
        self._records = self._load_records()
        self._file_state = self._load_state()

    def _load_records(self) -> dict[str, StoreRecord]:
        if not self._records_path.exists():
            return {}
        payload = json.loads(self._records_path.read_text(encoding="utf-8"))
        return {
            record_id: StoreRecord(
                id=record_id,
                document=record["document"],
                embedding=tuple(record["embedding"]),
                metadata=record["metadata"],
            )
            for record_id, record in payload.items()
        }

    def _load_state(self) -> dict[str, dict[str, Any]]:
        if not self._state_path.exists():
            return {}
        return json.loads(self._state_path.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        serializable_records = {
            record_id: {
                "document": record.document,
                "embedding": list(record.embedding),
                "metadata": record.metadata,
            }
            for record_id, record in self._records.items()
        }
        self._records_path.write_text(
            json.dumps(serializable_records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._state_path.write_text(
            json.dumps(self._file_state, indent=2, sort_keys=True),
            encoding="utf-8",
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
        self.delete(normalized_path, persist=False)

        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            record_id = f"{normalized_path}::{chunk_index}"
            self._records[record_id] = StoreRecord(
                id=record_id,
                document=chunk,
                embedding=embedding,
                metadata={
                    "path": normalized_path,
                    "mtime": mtime,
                    "chunk": chunk_index,
                    "mime": mime,
                    "size": size,
                },
            )

        self._file_state[normalized_path] = {"mtime": mtime, "size": size, "mime": mime}
        self._persist()

    def delete(self, file_path: str | Path, *, persist: bool = True) -> int:
        normalized_path = str(Path(file_path).resolve())
        keys_to_delete = [
            key for key, record in self._records.items() if record.metadata.get("path") == normalized_path
        ]
        for key in keys_to_delete:
            del self._records[key]
        self._file_state.pop(normalized_path, None)
        if persist:
            self._persist()
        return len(keys_to_delete)

    def is_stale(self, file_path: str | Path, *, mtime: float, size: int) -> bool:
        normalized_path = str(Path(file_path).resolve())
        current = self._file_state.get(normalized_path)
        if current is None:
            return True
        return current["mtime"] != mtime or current["size"] != size

    def query(
        self,
        embedding: tuple[float, ...],
        *,
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        active_filters = filters or {}
        candidates: list[dict[str, Any]] = []
        for record in self._records.values():
            if not _matches_filters(record.metadata, active_filters):
                continue
            candidates.append(
                {
                    "path": record.metadata["path"],
                    "score": cosine_similarity(record.embedding, embedding),
                    "chunk": record.metadata["chunk"],
                    "snippet": record.document[:240],
                    "mime": record.metadata["mime"],
                    "size": record.metadata["size"],
                    "mtime": record.metadata["mtime"],
                }
            )
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[:n_results]

    def stats(self) -> dict[str, int]:
        unique_paths = {record.metadata["path"] for record in self._records.values()}
        return {
            "documents": len(unique_paths),
            "chunks": len(self._records),
        }


def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    mime = filters.get("mime")
    if mime and metadata.get("mime") != mime:
        return False

    path_prefix = filters.get("path_prefix")
    if path_prefix and not str(metadata.get("path", "")).startswith(str(Path(path_prefix).resolve())):
        return False

    mtime_from = filters.get("mtime_from")
    if mtime_from is not None and float(metadata.get("mtime", 0.0)) < float(mtime_from):
        return False

    mtime_to = filters.get("mtime_to")
    if mtime_to is not None and float(metadata.get("mtime", 0.0)) > float(mtime_to):
        return False

    return True
