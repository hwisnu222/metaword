"""Metadata read/write tasks that run off the UI thread."""

from __future__ import annotations

import sys
from pathlib import Path

from exiftool import ExifToolHelper
from libs.keyworder import Keyworder
from PySide6.QtCore import QObject, QRunnable, Signal

from ui.metadata import metadata_summary


class CheckWorker(QRunnable):
    """Read metadata from a file without blocking the UI thread."""

    class Signals(QObject):
        done = Signal(object, bool, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = CheckWorker.Signals()

    def run(self) -> None:
        try:
            with ExifToolHelper() as et:
                result = et.get_metadata(str(self.path))

            found, message = metadata_summary(result[0] if result else {})
            self.signals.done.emit(self.path, found, message)
        except Exception as exc:  # pragma: no cover - depends on exiftool install
            self.signals.done.emit(self.path, False, f"Check failed: {exc}")


class AddMetadataWorker(QRunnable):
    """Run the existing Keyworder pipeline in the background."""

    class Signals(QObject):
        done = Signal(object, bool, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = AddMetadataWorker.Signals()

    def run(self) -> None:
        try:
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))

            result = Keyworder().analyze_image_for_shutterstock(str(self.path))
            if not result:
                self.signals.done.emit(self.path, False, "Failed to add metadata")
                return

            with ExifToolHelper() as et:
                metadata = et.get_metadata(str(self.path))
            found, _ = metadata_summary(metadata[0] if metadata else {})

            if found:
                self.signals.done.emit(self.path, True, "Metadata added")
            else:
                self.signals.done.emit(
                    self.path, False, "Generated metadata was not written"
                )
        except SystemExit:
            self.signals.done.emit(self.path, False, "GEMINI_API_KEY is not set")
        except Exception as exc:  # pragma: no cover - depends on runtime setup
            self.signals.done.emit(self.path, False, str(exc))


class MetadataWorker(QRunnable):
    """Read every metadata tag from a file without blocking the UI thread."""

    class Signals(QObject):
        done = Signal(object, object, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = MetadataWorker.Signals()

    def run(self) -> None:
        try:
            with ExifToolHelper() as et:
                result = et.get_metadata(str(self.path))
            self.signals.done.emit(self.path, result[0] if result else {}, "")
        except Exception as exc:  # pragma: no cover - depends on exiftool install
            self.signals.done.emit(self.path, {}, str(exc))
