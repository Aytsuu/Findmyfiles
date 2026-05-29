from __future__ import annotations

import logging
from pathlib import Path
from threading import Thread

import uvicorn

from findmyfiles.api import create_app
from findmyfiles.config import load_config
from findmyfiles.indexer import Indexer
from findmyfiles.runtime import ScanStatus
from findmyfiles.store import VectorStore
from findmyfiles.watcher import FileWatcher

logger = logging.getLogger("findmyfiles")


def _iter_files(root: Path, include_exts: tuple[str, ...]):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in include_exts:
            yield path


def _start_initial_scan(
    *,
    config_path: str | Path,
    indexer: Indexer,
    scan_status: ScanStatus,
) -> Thread:
    config = load_config(config_path)

    def run_initial_scan() -> None:
        scan_status.start()
        try:
            for root in config.watcher.roots:
                if not root.exists():
                    continue
                scan_status.set_root(str(root))
                print(f"[findmyfiles] initial scan started for {root}")
                for file_path in _iter_files(root, config.watcher.include_exts):
                    scan_status.record_seen(str(file_path))
                    if indexer.index_file(file_path) is not None:
                        scan_status.record_indexed()
                    if scan_status.snapshot().files_seen % 100 == 0:
                        snapshot = scan_status.snapshot()
                        print(
                            "[findmyfiles] initial scan progress: "
                            f"seen={snapshot.files_seen} indexed={snapshot.files_indexed} root={snapshot.current_root}"
                        )
            print("[findmyfiles] initial scan complete")
            scan_status.finish()
        except Exception as exc:
            scan_status.fail(str(exc))
            print(f"[findmyfiles] initial scan failed: {exc}")

    thread = Thread(target=run_initial_scan, name="findmyfiles-initial-scan", daemon=True)
    thread.start()
    return thread


def build_runtime(config_path: str | Path = "config.toml") -> tuple[object, FileWatcher, Indexer, ScanStatus]:
    config = load_config(config_path)
    store = VectorStore(
        config.storage.chroma_dir,
        collection_name=config.storage.collection_name,
    )
    indexer = Indexer(store, config.indexer, gemini_api_key=config.gemini_api_key)
    scan_status = ScanStatus()
    watcher = FileWatcher(config.watcher, indexer.index_file)
    app = create_app(config=config, store=store, indexer=indexer, scan_status=scan_status)
    return app, watcher, indexer, scan_status


def run(config_path: str | Path = "config.toml") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(message)s",
    )
    app, watcher, indexer, scan_status = build_runtime(config_path)
    watcher.start()
    _start_initial_scan(config_path=config_path, indexer=indexer, scan_status=scan_status)
    try:
        config = load_config(config_path)
        logger.info("api starting host=%s port=%s", config.api.host, config.api.port)
        uvicorn.run(app, host=config.api.host, port=config.api.port)
    finally:
        watcher.stop()


if __name__ == "__main__":
    run()
