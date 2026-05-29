from __future__ import annotations

from pathlib import Path
from threading import Lock, Timer
from typing import Callable

from findmyfiles.config import WatcherConfig

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover
    FileSystemEventHandler = object
    Observer = None


class DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self, config: WatcherConfig, on_path: Callable[[Path], None]) -> None:
        self.config = config
        self.on_path = on_path
        self._timers: dict[str, Timer] = {}
        self._lock = Lock()

    def on_created(self, event) -> None:  # type: ignore[override]
        self._schedule(event.src_path)

    def on_modified(self, event) -> None:  # type: ignore[override]
        self._schedule(event.src_path)

    def on_moved(self, event) -> None:  # type: ignore[override]
        self._schedule(event.dest_path)

    def on_deleted(self, event) -> None:  # type: ignore[override]
        self._schedule(event.src_path)

    def _schedule(self, raw_path: str) -> None:
        path = Path(raw_path)
        if path.is_dir():
            return
        if path.suffix.lower() not in self.config.include_exts:
            return
        if any(path.match(pattern) for pattern in self.config.exclude_globs):
            return

        with self._lock:
            timer = self._timers.pop(str(path), None)
            if timer is not None:
                timer.cancel()
            timer = Timer(self.config.settle_seconds, self.on_path, args=[path])
            self._timers[str(path)] = timer
            timer.start()


class FileWatcher:
    def __init__(self, config: WatcherConfig, on_path: Callable[[Path], None]) -> None:
        self.config = config
        self.on_path = on_path
        self._observer = None if Observer is None else Observer()
        self._watched_roots: tuple[Path, ...] = ()

    def start(self) -> None:
        if self._observer is None:
            return
        handler = DebouncedEventHandler(self.config, self.on_path)
        watched_roots: list[Path] = []
        for root in self.config.roots:
            if not root.exists():
                print(f"[findmyfiles] skipping missing watch root: {root}")
                continue
            self._observer.schedule(handler, str(root), recursive=True)
            watched_roots.append(root)
        self._watched_roots = tuple(watched_roots)
        if not self._watched_roots:
            print("[findmyfiles] no valid watch roots found; API will run without filesystem watching")
            return
        self._observer.start()

    def stop(self) -> None:
        if self._observer is None:
            return
        if not self._watched_roots:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
