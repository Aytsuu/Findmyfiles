from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ScanSnapshot:
    running: bool
    files_seen: int
    files_indexed: int
    current_root: str | None
    last_path: str | None
    error: str | None


class ScanStatus:
    def __init__(self) -> None:
        self._lock = Lock()
        self._running = False
        self._files_seen = 0
        self._files_indexed = 0
        self._current_root: str | None = None
        self._last_path: str | None = None
        self._error: str | None = None

    def start(self) -> None:
        with self._lock:
            self._running = True
            self._files_seen = 0
            self._files_indexed = 0
            self._current_root = None
            self._last_path = None
            self._error = None

    def set_root(self, root: str) -> None:
        with self._lock:
            self._current_root = root

    def record_seen(self, path: str) -> None:
        with self._lock:
            self._files_seen += 1
            self._last_path = path

    def record_indexed(self) -> None:
        with self._lock:
            self._files_indexed += 1

    def fail(self, error: str) -> None:
        with self._lock:
            self._running = False
            self._error = error

    def finish(self) -> None:
        with self._lock:
            self._running = False

    def snapshot(self) -> ScanSnapshot:
        with self._lock:
            return ScanSnapshot(
                running=self._running,
                files_seen=self._files_seen,
                files_indexed=self._files_indexed,
                current_root=self._current_root,
                last_path=self._last_path,
                error=self._error,
            )
