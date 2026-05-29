from __future__ import annotations

from pathlib import Path

from findmyfiles.config import WatcherConfig
from findmyfiles.watcher import FileWatcher


class FakeObserver:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, bool]] = []
        self.started = False
        self.stopped = False
        self.joined = False

    def schedule(self, handler, path: str, recursive: bool) -> None:
        self.scheduled.append((path, recursive))

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout: int) -> None:
        self.joined = True


def test_watcher_skips_missing_roots(tmp_path: Path, capsys) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"

    watcher = FileWatcher(
        WatcherConfig(
            roots=(missing, existing),
            exclude_globs=(),
            include_exts=(".txt",),
        ),
        lambda path: None,
    )
    fake_observer = FakeObserver()
    watcher._observer = fake_observer

    watcher.start()

    assert fake_observer.started is True
    assert fake_observer.scheduled == [(str(existing), True)]
    output = capsys.readouterr().out
    assert "skipping missing watch root" in output


def test_watcher_does_not_start_without_valid_roots(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing"
    watcher = FileWatcher(
        WatcherConfig(
            roots=(missing,),
            exclude_globs=(),
            include_exts=(".txt",),
        ),
        lambda path: None,
    )
    fake_observer = FakeObserver()
    watcher._observer = fake_observer

    watcher.start()
    watcher.stop()

    assert fake_observer.started is False
    assert fake_observer.stopped is False
    assert "no valid watch roots found" in capsys.readouterr().out
