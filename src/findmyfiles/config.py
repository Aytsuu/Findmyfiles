from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib
from typing import Any


@dataclass(frozen=True)
class WatcherConfig:
    roots: tuple[Path, ...]
    exclude_globs: tuple[str, ...]
    include_exts: tuple[str, ...]
    settle_seconds: float = 2.0


@dataclass(frozen=True)
class IndexerConfig:
    batch_size: int = 20
    chunk_tokens: int = 500
    chunk_overlap: int = 50
    model: str = "models/gemini-embedding-002"


@dataclass(frozen=True)
class APIConfig:
    host: str = "127.0.0.1"
    port: int = 7474


@dataclass(frozen=True)
class StorageConfig:
    chroma_dir: Path


@dataclass(frozen=True)
class AppConfig:
    watcher: WatcherConfig
    indexer: IndexerConfig
    api: APIConfig
    storage: StorageConfig
    gemini_api_key: str | None = None


def _expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def _get_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    section = data.get(key, {})
    if not isinstance(section, dict):
        msg = f"config section '{key}' must be a table"
        raise ValueError(msg)
    return section


def load_config(path: str | Path = "config.toml") -> AppConfig:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    watcher_data = _get_section(raw, "watcher")
    indexer_data = _get_section(raw, "indexer")
    api_data = _get_section(raw, "api")
    storage_data = _get_section(raw, "storage")

    roots = tuple(_expand_path(root) for root in watcher_data.get("roots", ()))
    if not roots:
        raise ValueError("watcher.roots must contain at least one directory")

    include_exts = tuple(ext.lower() for ext in watcher_data.get("include_exts", ()))
    if not include_exts:
        raise ValueError("watcher.include_exts must contain at least one file extension")

    watcher = WatcherConfig(
        roots=roots,
        exclude_globs=tuple(watcher_data.get("exclude_globs", ())),
        include_exts=include_exts,
        settle_seconds=float(watcher_data.get("settle_seconds", 2.0)),
    )
    indexer = IndexerConfig(
        batch_size=int(indexer_data.get("batch_size", 20)),
        chunk_tokens=int(indexer_data.get("chunk_tokens", 500)),
        chunk_overlap=int(indexer_data.get("chunk_overlap", 50)),
        model=str(indexer_data.get("model", "models/gemini-embedding-002")),
    )
    api = APIConfig(
        host=str(api_data.get("host", "127.0.0.1")),
        port=int(api_data.get("port", 7474)),
    )
    storage = StorageConfig(
        chroma_dir=_expand_path(str(storage_data.get("chroma_dir", "~/.findmyfiles/chroma"))),
    )
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    return AppConfig(
        watcher=watcher,
        indexer=indexer,
        api=api,
        storage=storage,
        gemini_api_key=gemini_api_key,
    )
