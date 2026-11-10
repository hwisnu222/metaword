"""Dark-mode metadata manager window built with PySide6.

Run it from the project root with::

    python ui/window.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from exiftool import ExifToolHelper
from libs.keyworder import Keyworder

from PySide6.QtCore import (
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

PRIMARY = "#3B82F6"

IMAGE_EXTENSIONS = {
    ".ai",
    ".avif",
    ".bmp",
    ".eps",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".psd",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}

# Pillow opens these directly; .eps additionally requires Ghostscript.
# .ai/.svg are vector-only and .heic needs pillow-heif, so skip those.
GENERATABLE_EXTENSIONS = IMAGE_EXTENSIONS - {".ai", ".heic", ".svg"}

STATUS_COLORS = {
    "info": "#60A5FA",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
    "muted": "#64748B",
}

STYLE_SHEET = """
QWidget#root {
    background-color: #0B1220;
    border: 1px solid #1B2738;
}
QWidget#content {
    background-color: transparent;
}

QFrame#titleBar {
    background-color: #0F172A;
    border-bottom: 1px solid #1B2738;
}
QLabel#logo {
    background-color: #3B82F6;
    color: #FFFFFF;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 800;
}
QLabel#appTitle {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 700;
}
QLabel#appSubtitle {
    color: #64748B;
    font-size: 10px;
}
QToolButton#windowButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #94A3B8;
    font-size: 14px;
}
QToolButton#windowButton:hover {
    background-color: #1E293B;
    color: #F8FAFC;
}
QToolButton#closeButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #94A3B8;
    font-size: 13px;
}
QToolButton#closeButton:hover {
    background-color: #DC2626;
    color: #FFFFFF;
}

QLabel#pageTitle {
    color: #F8FAFC;
    font-size: 24px;
    font-weight: 700;
}
QLabel#pathLabel {
    color: #64748B;
    font-size: 11px;
}
QLabel#countBadge {
    background-color: #16283F;
    border: 1px solid #24466F;
    border-radius: 10px;
    color: #93C5FD;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 10px;
}

QPushButton#primaryButton {
    background-color: #3B82F6;
    border: none;
    border-radius: 7px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 700;
    padding: 7px 14px;
}
QPushButton#primaryButton:hover {
    background-color: #2563EB;
}
QPushButton#primaryButton:pressed {
    background-color: #1D4ED8;
}
QPushButton#primaryButton:disabled {
    background-color: #16202F;
    color: #4B5B70;
}
QPushButton#primaryButton:focus {
    border: 1px solid #93C5FD;
}

QPushButton#secondaryButton {
    background-color: #121C2B;
    border: 1px solid #263449;
    border-radius: 7px;
    color: #CBD5E1;
    font-size: 12px;
    font-weight: 600;
    padding: 7px 14px;
}
QPushButton#secondaryButton:hover {
    background-color: #1B2738;
    border-color: #3B82F6;
    color: #F8FAFC;
}
QPushButton#secondaryButton:pressed {
    background-color: #0F172A;
}
QPushButton#secondaryButton:focus {
    border-color: #3B82F6;
    color: #F8FAFC;
}
QPushButton#secondaryButton:disabled {
    background-color: #0F172A;
    border-color: #1B2738;
    color: #475569;
}

QLineEdit#searchInput {
    background-color: #111B2B;
    border: 1px solid #243244;
    border-radius: 8px;
    color: #E2E8F0;
    font-size: 12px;
    padding: 0 12px;
    selection-background-color: #2563EB;
}
QLineEdit#searchInput:focus {
    border-color: #3B82F6;
}
QLineEdit#searchInput QToolButton {
    background-color: transparent;
    border: none;
}

QScrollArea#scrollArea {
    background-color: transparent;
    border: none;
}
QScrollArea#scrollArea > QWidget > QWidget {
    background-color: transparent;
}
QWidget#listContainer {
    background-color: transparent;
}
QScrollBar:vertical {
    background: transparent;
    margin: 2px;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2A3A52;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: #3B82F6;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QFrame#fileRow {
    background-color: #121C2B;
    border: 1px solid #1F2C40;
    border-radius: 10px;
}
QFrame#fileRow:hover {
    background-color: #162235;
    border-color: #2E405C;
}
QLabel#fileBadge[kind="image"] {
    background-color: #16283F;
    border: 1px solid #24466F;
    border-radius: 9px;
    color: #93C5FD;
    font-size: 9px;
    font-weight: 800;
}
QLabel#fileBadge[kind="file"] {
    background-color: #1A2433;
    border: 1px solid #2A3A50;
    border-radius: 9px;
    color: #94A3B8;
    font-size: 9px;
    font-weight: 800;
}
QLabel#fileName {
    color: #F1F5F9;
    font-size: 13px;
    font-weight: 600;
}
QLabel#fileMeta {
    color: #64748B;
    font-size: 11px;
}
QLabel#fileStatus {
    font-size: 11px;
}
QLabel#emptyState {
    color: #475569;
    font-size: 13px;
}

QFrame#statusBar {
    background-color: #0F172A;
    border-top: 1px solid #1B2738;
}
QLabel#statusText {
    color: #94A3B8;
    font-size: 11px;
}
QLabel#statusMeta {
    color: #475569;
    font-size: 11px;
}

QDialog#dialogRoot {
    background-color: #0B1220;
    border: 1px solid #1B2738;
}
QFrame#dialogHeader {
    background-color: #0F172A;
    border-bottom: 1px solid #1B2738;
}
QLabel#dialogTitle {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 700;
}
QLabel#dialogSubtitle {
    color: #64748B;
    font-size: 10px;
}
QScrollArea#dialogScroll {
    background-color: transparent;
    border: none;
}
QScrollArea#dialogScroll > QWidget > QWidget {
    background-color: transparent;
}
QWidget#dialogContent {
    background-color: transparent;
}
QLabel#sectionTitle {
    color: #93C5FD;
    font-size: 11px;
    font-weight: 700;
}
QFrame#metadataCard {
    background-color: #121C2B;
    border: 1px solid #1F2C40;
    border-radius: 10px;
}
QLabel#fieldLabel {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
}
QLabel#metadataKey {
    color: #64748B;
    font-size: 10px;
    font-weight: 700;
}
QLabel#metadataValue {
    color: #E2E8F0;
    font-size: 12px;
}
QLabel#metadataValue[empty="true"] {
    color: #475569;
    font-style: italic;
}
QLineEdit#fieldInput,
QTextEdit#fieldInput {
    background-color: #111B2B;
    border: 1px solid #243244;
    border-radius: 8px;
    color: #E2E8F0;
    font-size: 12px;
    padding: 8px;
    selection-background-color: #2563EB;
}
QLineEdit#fieldInput:focus,
QTextEdit#fieldInput:focus {
    border-color: #3B82F6;
}
QLabel#errorText {
    color: #F87171;
    font-size: 11px;
}

QToolTip {
    background-color: #1E293B;
    border: 1px solid #334155;
    color: #E2E8F0;
    padding: 5px 8px;
}
QMenu {
    background-color: #121C2B;
    border: 1px solid #263449;
    color: #E2E8F0;
    padding: 4px;
}
QMenu::item {
    border-radius: 4px;
    padding: 5px 18px;
}
QMenu::item:selected {
    background-color: #1E3A5F;
    color: #F8FAFC;
}
QMenu::separator {
    background-color: #263449;
    height: 1px;
    margin: 4px 8px;
}
"""


def dark_palette() -> QPalette:
    """Return a palette for widgets Qt draws itself (menus, tooltips, ...)."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0B1220"))
    palette.setColor(QPalette.WindowText, QColor("#E2E8F0"))
    palette.setColor(QPalette.Base, QColor("#111B2B"))
    palette.setColor(QPalette.AlternateBase, QColor("#16202F"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1E293B"))
    palette.setColor(QPalette.ToolTipText, QColor("#E2E8F0"))
    palette.setColor(QPalette.Text, QColor("#E2E8F0"))
    palette.setColor(QPalette.Button, QColor("#121C2B"))
    palette.setColor(QPalette.ButtonText, QColor("#E2E8F0"))
    palette.setColor(QPalette.BrightText, QColor("#F87171"))
    palette.setColor(QPalette.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor("#64748B"))

    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        palette.setColor(QPalette.Disabled, role, QColor("#475569"))

    return palette


def clear_icon(size: int = 16) -> QIcon:
    """Build a light close icon so it stays visible on the dark search field."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor("#94A3B8"), 1.6)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    margin = 4
    painter.drawLine(margin, margin, size - margin, size - margin)
    painter.drawLine(size - margin, margin, margin, size - margin)
    painter.end()

    return QIcon(pixmap)


def human_size(size: int) -> str:
    """Return a compact, human readable file size."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def metadata_summary(metadata: dict) -> tuple[bool, str]:
    """Inspect an ExifTool metadata dict and describe its metadata state."""
    title = (
        metadata.get("XMP:Title")
        or metadata.get("Title")
        or metadata.get("Headline")
        or metadata.get("IPTC:Headline")
    )
    keywords = (
        metadata.get("Keywords")
        or metadata.get("IPTC:Keywords")
        or metadata.get("XMP:Subject")
        or metadata.get("Subject")
    )

    if isinstance(keywords, str):
        tags = [item.strip() for item in keywords.split(",") if item.strip()]
    elif isinstance(keywords, (list, tuple)):
        tags = [str(item).strip() for item in keywords if str(item).strip()]
    else:
        tags = []

    description = (
        metadata.get("XMP:Description")
        or metadata.get("Description")
        or metadata.get("Caption-Abstract")
        or metadata.get("IPTC:Caption-Abstract")
    )

    if not (title or description or tags):
        return False, "No metadata"
    if tags:
        return True, f"Metadata found · {len(tags)} tags"
    return True, "Metadata found"


def first_metadata_value(metadata: dict, *keys: str) -> str:
    """Return the first non-empty metadata value for the given tag names."""
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts = [str(item).strip() for item in value if str(item).strip()]
            if parts:
                return ", ".join(parts)
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def metadata_edit_values(metadata: dict) -> dict[str, str]:
    """Map raw ExifTool tags to the fields shown in the preview and editor."""
    return {
        "title": first_metadata_value(
            metadata, "XMP:Title", "Title", "Headline", "IPTC:Headline"
        ),
        "description": first_metadata_value(
            metadata,
            "XMP:Description",
            "Description",
            "Caption-Abstract",
            "IPTC:Caption-Abstract",
        ),
        "keywords": first_metadata_value(
            metadata, "XMP:Subject", "Keywords", "IPTC:Keywords", "Subject"
        ),
        "categories": first_metadata_value(
            metadata,
            "XMP:Categories",
            "Categories",
            "IPTC:Categories",
            "IPTC:Category",
            "XMP:Category",
        ),
    }


def split_metadata_list(text: str) -> list[str]:
    """Turn a comma or newline separated field into a list of values."""
    normalized = text.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def write_metadata_values(path: Path, values: dict[str, str]) -> None:
    """Write the editable fields back to the file, replacing existing values."""
    keywords = split_metadata_list(values["keywords"])
    categories = split_metadata_list(values["categories"])
    tags: dict[str, object] = {
        "Headline": values["title"],
        "Description": values["description"],
        "Caption-Abstract": values["description"],
        "Keywords": keywords or "",
        "Categories": categories or "",
        "XMP:Title": values["title"],
        "XMP:Description": values["description"],
        "XMP:Subject": keywords or "",
    }

    with ExifToolHelper() as et:
        et.set_tags([str(path)], tags=tags, params=["-overwrite_original"])


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
            from exiftool import ExifToolHelper

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
            root = Path(__file__).resolve().parent.parent
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


class CheckBox(QCheckBox):
    """A QCheckBox with a custom-painted, blue-accented indicator."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumHeight(24)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self.text()) + 28, max(24, metrics.height() + 4))

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        checked = self.isChecked()
        hovered = self.underMouse()
        focused = self.hasFocus()
        enabled = self.isEnabled()

        indicator = QRect(1, (self.height() - 16) // 2, 16, 16)
        if not enabled:
            border = QColor("#263449")
            fill = QColor("#1E3A5F" if checked else "#111B2B")
        else:
            border = QColor(PRIMARY if checked or hovered or focused else "#334155")
            fill = QColor(PRIMARY if checked else "#0B1220")

        painter.setPen(QPen(border, 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(indicator, 4, 4)

        if checked:
            pen = QPen(QColor("#FFFFFF" if enabled else "#64748B"), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(
                [
                    QPointF(indicator.left() + 4.0, indicator.top() + 8.2),
                    QPointF(indicator.left() + 7.0, indicator.top() + 11.2),
                    QPointF(indicator.left() + 12.2, indicator.top() + 5.0),
                ]
            )

        if not enabled:
            text_color = QColor("#475569")
        else:
            text_color = QColor("#E2E8F0" if hovered or checked else "#94A3B8")
        painter.setPen(text_color)
        painter.drawText(
            self.rect().adjusted(26, 0, 0, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text(),
        )


class FileRow(QFrame):
    """One file entry with a metadata check and per-file metadata actions."""

    add_requested = Signal(object)
    check_toggled = Signal(object, bool)
    preview_requested = Signal(object)
    edit_requested = Signal(object)

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self.is_image = path.suffix.lower() in IMAGE_EXTENSIONS
        self.can_generate = path.suffix.lower() in GENERATABLE_EXTENSIONS
        self.can_edit = self.is_image
        self.setObjectName("fileRow")
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        badge = QLabel(path.suffix.lstrip(".").upper()[:4] or "FILE")
        badge.setObjectName("fileBadge")
        badge.setProperty("kind", "image" if self.is_image else "file")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        name = QLabel(path.name)
        name.setObjectName("fileName")
        name.setToolTip(str(path))
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        info.addWidget(name)

        try:
            stat = path.stat()
            details = f"{human_size(stat.st_size)}  ·  modified {self._format_time(stat.st_mtime)}"
        except OSError:
            details = "Unavailable"
        meta = QLabel(details)
        meta.setObjectName("fileMeta")
        info.addWidget(meta)

        self.status_label = QLabel("")
        self.status_label.setObjectName("fileStatus")
        self.status_label.setFixedHeight(14)
        info.addWidget(self.status_label)

        layout.addLayout(info, 1)

        self.checkbox = CheckBox("Check metadata")
        self.checkbox.setToolTip("Check whether this file already contains metadata")
        self.checkbox.toggled.connect(
            lambda checked: self.check_toggled.emit(self.path, checked)
        )
        layout.addWidget(self.checkbox, 0, Qt.AlignVCenter)

        self.preview_button = QPushButton("Preview")
        self.preview_button.setObjectName("secondaryButton")
        self.preview_button.setCursor(Qt.PointingHandCursor)
        self.preview_button.setMinimumWidth(74)
        self.preview_button.setToolTip("Preview every metadata tag stored in this file")
        self.preview_button.clicked.connect(
            lambda: self.preview_requested.emit(self.path)
        )
        layout.addWidget(self.preview_button, 0, Qt.AlignVCenter)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setObjectName("secondaryButton")
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.setMinimumWidth(62)
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self.path))
        if self.can_edit:
            self.edit_button.setToolTip("Edit this file's title, description and tags")
        else:
            self.edit_button.setEnabled(False)
            self.edit_button.setToolTip(
                "This file type does not support metadata editing"
            )
        layout.addWidget(self.edit_button, 0, Qt.AlignVCenter)

        self.add_button = QPushButton("Add Metadata")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setMinimumWidth(118)
        self.add_button.clicked.connect(lambda: self.add_requested.emit(self.path))
        if not self.can_generate:
            self.add_button.setEnabled(False)
            self.add_button.setToolTip("This format is not supported by the generator")
        layout.addWidget(self.add_button, 0, Qt.AlignVCenter)

    @staticmethod
    def _format_time(timestamp: float) -> str:
        from datetime import datetime

        return datetime.fromtimestamp(timestamp).strftime("%d %b %Y, %H:%M")

    def set_status(self, text: str, tone: str = "muted") -> None:
        color = STATUS_COLORS.get(tone, STATUS_COLORS["muted"])
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setToolTip(text)
        self.status_label.setText(text)

    def set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy and self.can_generate)
        self.add_button.setText("Adding…" if busy else "Add Metadata")
        self.checkbox.setEnabled(not busy)
        self.preview_button.setEnabled(not busy)
        self.edit_button.setEnabled(not busy and self.can_edit)

    def set_reading(self, reading: bool) -> None:
        self.add_button.setEnabled(not reading and self.can_generate)
        self.preview_button.setEnabled(not reading)
        self.edit_button.setEnabled(not reading and self.can_edit)

    def matches(self, query: str) -> bool:
        return query in self.path.name.casefold()


class TitleBar(QFrame):
    """Custom dark title bar for the frameless window."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        logo = QLabel("M")
        logo.setObjectName("logo")
        logo.setFixedSize(26, 26)
        logo.setAlignment(Qt.AlignCenter)
        logo.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Metaword")
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        subtitle = QLabel("Metadata manager")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        titles.addWidget(title)
        titles.addWidget(subtitle)

        layout.addWidget(logo)
        layout.addLayout(titles)
        layout.addStretch(1)

        minimize = self._window_button("—", "Minimize")
        maximize = self._window_button("□", "Maximize")
        close = self._window_button("✕", "Close", close=True)

        minimize.clicked.connect(window.showMinimized)
        maximize.clicked.connect(self._toggle_maximize)
        close.clicked.connect(window.close)

        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)

    def _window_button(self, text: str, tooltip: str, close: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("closeButton" if close else "windowButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(34, 28)
        return button

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            if self._window.isMaximized():
                self._window.showNormal()
                self._drag_offset = QPoint(self._window.width() // 2, 28)
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class DialogHeader(QFrame):
    """Compact draggable header for the frameless metadata dialogs."""

    def __init__(self, title: str, subtitle: str, dialog: QWidget) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setObjectName("dialogHeader")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("dialogSubtitle")
        subtitle_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        subtitle_label.setToolTip(subtitle)
        subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        titles.addWidget(title_label)
        titles.addWidget(subtitle_label)

        close = QToolButton()
        close.setObjectName("closeButton")
        close.setText("✕")
        close.setToolTip("Close")
        close.setCursor(Qt.PointingHandCursor)
        close.setFixedSize(34, 28)
        close.clicked.connect(dialog.reject)

        layout.addLayout(titles, 1)
        layout.addWidget(close)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()


class MetadataDialog(QDialog):
    """Shared frameless shell for the metadata preview and editor dialogs."""

    def __init__(
        self,
        path: Path,
        title: str,
        size: QSize,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.setObjectName("dialogRoot")
        self.setWindowTitle(f"{title} — {path.name}")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setPalette(dark_palette())
        self.setStyleSheet(STYLE_SHEET)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(size)
        self.setMinimumSize(540, 440)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(DialogHeader(title, path.name, self))

        self.body = QVBoxLayout()
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(14)
        root.addLayout(self.body, 1)


class MetadataPreviewDialog(MetadataDialog):
    """Read-only dialog showing key fields and every raw metadata tag."""

    def __init__(
        self,
        path: Path,
        metadata: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(path, "Metadata preview", QSize(720, 620), parent)
        values = metadata_edit_values(metadata)

        scroll = QScrollArea()
        scroll.setObjectName("dialogScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(16)

        if metadata:
            content_layout.addWidget(self._build_key_card(metadata, values))
            content_layout.addWidget(self._build_all_tags(metadata))
        else:
            empty = QLabel("No metadata found on this file.")
            empty.setObjectName("emptyState")
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(200)
            content_layout.addWidget(empty)

        content_layout.addStretch(1)
        scroll.setWidget(content)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setObjectName("secondaryButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)

        self.body.addWidget(scroll, 1)
        self.body.addLayout(footer)

    def _build_key_card(self, metadata: dict, values: dict[str, str]) -> QFrame:
        card = QFrame()
        card.setObjectName("metadataCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        heading.setSpacing(8)
        title = QLabel("Key metadata")
        title.setObjectName("sectionTitle")
        count = QLabel(f"{len(metadata)} tags")
        count.setObjectName("countBadge")
        heading.addWidget(title)
        heading.addWidget(count, 0, Qt.AlignVCenter)
        heading.addStretch(1)
        layout.addLayout(heading)

        for label, key in (
            ("Title", "title"),
            ("Description", "description"),
            ("Keywords", "keywords"),
            ("Categories", "categories"),
        ):
            layout.addLayout(self._field_block(label, values[key]))

        return card

    def _build_all_tags(self, metadata: dict) -> QWidget:
        container = QWidget()
        container.setObjectName("dialogContent")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("All tags")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        row = 0
        for key in sorted(metadata, key=str.casefold):
            value = first_metadata_value(metadata, key)
            if not value:
                continue

            key_label = QLabel(key)
            key_label.setObjectName("metadataKey")
            key_label.setWordWrap(True)
            key_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

            value_label = QLabel(value)
            value_label.setObjectName("metadataValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

            grid.addWidget(key_label, row, 0)
            grid.addWidget(value_label, row, 1)
            row += 1

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return container

    @staticmethod
    def _field_block(label: str, value: str) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(2)

        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")

        value_label = QLabel(value or "Not set")
        value_label.setObjectName("metadataValue")
        value_label.setProperty("empty", "false" if value else "true")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        block.addWidget(field_label)
        block.addWidget(value_label)
        return block


class MetadataEditDialog(MetadataDialog):
    """Form dialog that writes title, description, keywords and categories."""

    saved = Signal(object)

    def __init__(
        self,
        path: Path,
        metadata: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(path, "Edit metadata", QSize(660, 660), parent)
        self.setMinimumSize(560, 600)
        values = metadata_edit_values(metadata)

        self.title_input = QLineEdit(values["title"])
        self.title_input.setObjectName("fieldInput")
        self.title_input.setPlaceholderText("Add a title")
        self.title_input.setClearButtonEnabled(True)
        self.body.addWidget(self._field("Title", self.title_input))

        self.description_input = QTextEdit()
        self.description_input.setObjectName("fieldInput")
        self.description_input.setPlaceholderText("Describe the file")
        self.description_input.setPlainText(values["description"])
        self.description_input.setFixedHeight(108)
        self.body.addWidget(self._field("Description", self.description_input))

        self.keywords_input = QTextEdit()
        self.keywords_input.setObjectName("fieldInput")
        self.keywords_input.setPlaceholderText("keyword one, keyword two")
        self.keywords_input.setPlainText(values["keywords"])
        self.keywords_input.setFixedHeight(78)
        self.body.addWidget(self._field("Keywords", self.keywords_input))

        self.categories_input = QLineEdit(values["categories"])
        self.categories_input.setObjectName("fieldInput")
        self.categories_input.setPlaceholderText("category one, category two")
        self.categories_input.setClearButtonEnabled(True)
        self.body.addWidget(self._field("Categories", self.categories_input))

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorText")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.body.addWidget(self.error_label)

        footer = QHBoxLayout()
        footer.addStretch(1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)

        self.save_button = QPushButton("Save changes")
        self.save_button.setObjectName("primaryButton")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.save_button)

        self.body.addLayout(footer)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._save)
        self.title_input.setFocus()

    def _field(self, label: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setObjectName("dialogContent")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")
        field_label.setBuddy(widget)

        layout.addWidget(field_label)
        layout.addWidget(widget)
        return container

    def _save(self) -> None:
        if not self.path.exists():
            self._show_error("This file no longer exists.")
            return

        values = {
            "title": self.title_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "keywords": self.keywords_input.toPlainText().strip(),
            "categories": self.categories_input.text().strip(),
        }

        try:
            write_metadata_values(self.path, values)
        except Exception as exc:  # pragma: no cover - depends on exiftool install
            self._show_error(f"Could not save metadata: {exc}")
            return

        self.saved.emit(self.path)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()


class MetadataWindow(QWidget):
    """Main window: lists the current directory with per-file metadata actions."""

    def __init__(self, directory: Path | None = None) -> None:
        super().__init__()
        self.directory = Path(directory or Path.cwd()).resolve()
        self._rows: list[FileRow] = []
        self._rows_by_path: dict[Path, FileRow] = {}
        self._check_workers: dict[Path, CheckWorker] = {}
        self._add_workers: dict[Path, AddMetadataWorker] = {}
        self._metadata_workers: dict[Path, MetadataWorker] = {}
        self._pending_metadata_action: dict[Path, str] = {}
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(4)

        self.setWindowTitle("Metaword — Metadata Manager")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setPalette(dark_palette())
        self.resize(1000, 720)
        self.setMinimumSize(780, 560)

        self._build_ui()
        self.setStyleSheet(STYLE_SHEET)
        self._install_shortcuts()
        self.refresh()

    def _build_ui(self) -> None:
        self.setObjectName("root")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(TitleBar(self))

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 16)
        content_layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)

        heading = QVBoxLayout()
        heading.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        page_title = QLabel("Files")
        page_title.setObjectName("pageTitle")
        self.count_badge = QLabel("0 files")
        self.count_badge.setObjectName("countBadge")
        title_row.addWidget(page_title)
        title_row.addWidget(self.count_badge, 0, Qt.AlignVCenter)
        title_row.addStretch(1)
        heading.addLayout(title_row)

        self.path_label = QLabel(str(self.directory))
        self.path_label.setObjectName("pathLabel")
        self.path_label.setToolTip(str(self.directory))
        heading.addWidget(self.path_label)
        header.addLayout(heading, 1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button, 0, Qt.AlignTop)

        content_layout.addLayout(header)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search files…")
        self.search_input.setFixedHeight(38)

        self.clear_action = self.search_input.addAction(
            clear_icon(), QLineEdit.TrailingPosition
        )
        self.clear_action.setToolTip("Clear search")
        self.clear_action.setVisible(False)
        self.clear_action.triggered.connect(self.search_input.clear)
        self.search_input.textChanged.connect(self._on_search_changed)

        content_layout.addWidget(self.search_input)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.list_container = QWidget()
        self.list_container.setObjectName("listContainer")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(8)

        self.empty_label = QLabel("This folder is empty")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(220)
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch(1)

        self.scroll.setWidget(self.list_container)
        content_layout.addWidget(self.scroll, 1)

        root.addWidget(content, 1)
        root.addWidget(self._build_status_bar())

    def _build_status_bar(self) -> QFrame:
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(38)

        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(24, 0, 12, 0)
        layout.setSpacing(8)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(
            f"color: {STATUS_COLORS['info']}; font-size: 9px;"
        )
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusText")
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("statusMeta")

        layout.addWidget(self.status_dot)
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.summary_label)

        grip = QSizeGrip(status_bar)
        grip.setFixedSize(16, 16)
        layout.addWidget(grip, 0, Qt.AlignBottom)

        return status_bar

    def _install_shortcuts(self) -> None:
        for sequence, handler in (
            ("Ctrl+Q", self.close),
            ("F5", self.refresh),
            ("Ctrl+F", self.search_input.setFocus),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)

    def refresh(self) -> None:
        self._clear_rows()
        try:
            files = [
                path
                for path in self.directory.iterdir()
                if path.is_file() and not path.name.startswith(".")
            ]
        except OSError as exc:
            self._filter_rows()
            self.set_status(f"Cannot read directory: {exc}", "error")
            return

        files.sort(
            key=lambda path: (
                path.suffix.lower() not in IMAGE_EXTENSIONS,
                path.name.casefold(),
            )
        )

        for path in files:
            self._add_row(path)

        self._filter_rows()
        self.set_status(f"Loaded {len(files)} files from {self.directory}", "info")

    def _clear_rows(self) -> None:
        for row in self._rows:
            self.list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._rows_by_path.clear()

    def _add_row(self, path: Path) -> None:
        row = FileRow(path)
        row.add_requested.connect(self._on_add_requested)
        row.check_toggled.connect(self._on_check_toggled)
        row.preview_requested.connect(self._on_preview_requested)
        row.edit_requested.connect(self._on_edit_requested)
        self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self._rows.append(row)
        self._rows_by_path[path] = row

    def _on_search_changed(self, text: str) -> None:
        self.clear_action.setVisible(bool(text))
        self._filter_rows()

    def _filter_rows(self) -> None:
        query = self.search_input.text().strip().casefold()
        visible = 0
        for row in self._rows:
            show = not query or row.matches(query)
            row.setVisible(show)
            visible += int(show)

        suffix = "" if visible == 1 else "s"
        self.count_badge.setText(f"{visible} file{suffix}")

        if not self._rows:
            self.empty_label.setText("This folder is empty")
            self.empty_label.show()
        elif visible == 0:
            self.empty_label.setText("No files match your search")
            self.empty_label.show()
        else:
            self.empty_label.hide()

        total = len(self._rows)
        self.summary_label.setText(
            f"{visible} of {total} shown" if query else f"{total} total"
        )

    def _on_check_toggled(self, path: Path, checked: bool) -> None:
        row = self._rows_by_path.get(path)
        if row is None:
            return

        if not checked:
            row.set_status("")
            return

        row.set_status("Checking metadata…", "info")
        if path in self._check_workers:
            return

        worker = CheckWorker(path)
        worker.signals.done.connect(self._on_check_done)
        self._check_workers[path] = worker
        self._thread_pool.start(worker)

    def _on_check_done(self, path: Path, found: bool, message: str) -> None:
        self._check_workers.pop(path, None)
        row = self._rows_by_path.get(path)
        if row is None or not row.checkbox.isChecked():
            return

        row.set_status(message, "success" if found else "warning")
        self.set_status(f"{path.name}: {message}", "success" if found else "warning")

    def _on_preview_requested(self, path: Path) -> None:
        self._start_metadata_action(path, "preview")

    def _on_edit_requested(self, path: Path) -> None:
        self._start_metadata_action(path, "edit")

    def _start_metadata_action(self, path: Path, action: str) -> None:
        row = self._rows_by_path.get(path)
        if row is None or path in self._metadata_workers:
            return

        row.set_reading(True)
        row.set_status("Reading metadata…", "info")
        self.set_status(f"Reading metadata from {path.name}…", "info")

        worker = MetadataWorker(path)
        worker.signals.done.connect(self._on_metadata_loaded)
        self._metadata_workers[path] = worker
        self._pending_metadata_action[path] = action
        self._thread_pool.start(worker)

    def _on_metadata_loaded(self, path: Path, metadata: dict, error: str) -> None:
        self._metadata_workers.pop(path, None)
        action = self._pending_metadata_action.pop(path, "preview")
        row = self._rows_by_path.get(path)
        if row is not None:
            row.set_reading(False)

        if error:
            message = f"Could not read metadata: {error}"
            if row is not None:
                row.set_status(message, "error")
            self.set_status(f"{path.name}: {message}", "error")
            return

        if row is not None:
            row.set_status("")

        if action == "edit":
            self.set_status(f"Editing metadata for {path.name}", "info")
            self._open_edit_dialog(path, metadata)
        else:
            self.set_status(f"Previewing metadata for {path.name}", "info")
            self._open_preview_dialog(path, metadata)

    def _open_preview_dialog(self, path: Path, metadata: dict) -> None:
        dialog = MetadataPreviewDialog(path, metadata, self)
        dialog.exec()

    def _open_edit_dialog(self, path: Path, metadata: dict) -> None:
        dialog = MetadataEditDialog(path, metadata, self)
        dialog.saved.connect(self._on_metadata_saved)
        dialog.exec()

    def _on_metadata_saved(self, path: Path) -> None:
        row = self._rows_by_path.get(path)
        if row is None:
            return

        row.set_status("Metadata updated", "success")
        row.checkbox.blockSignals(True)
        row.checkbox.setChecked(True)
        row.checkbox.blockSignals(False)
        self.set_status(f"Metadata updated for {path.name}", "success")

    def _on_add_requested(self, path: Path) -> None:
        row = self._rows_by_path.get(path)
        if row is None:
            return

        row.set_busy(True)
        row.set_status("Generating metadata…", "info")
        if path in self._add_workers:
            return

        self.set_status(f"Generating metadata for {path.name}…", "info")

        worker = AddMetadataWorker(path)
        worker.signals.done.connect(self._on_add_done)
        self._add_workers[path] = worker
        self._thread_pool.start(worker)

    def _on_add_done(self, path: Path, success: bool, message: str) -> None:
        self._add_workers.pop(path, None)
        row = self._rows_by_path.get(path)
        if row is None:
            return

        row.set_busy(False)
        if success:
            row.set_status("Metadata added", "success")
            row.checkbox.blockSignals(True)
            row.checkbox.setChecked(True)
            row.checkbox.blockSignals(False)
            self.set_status(f"Metadata added to {path.name}", "success")
        else:
            row.set_status(message, "error")
            self.set_status(f"{path.name}: {message}", "error")

    def set_status(self, text: str, tone: str = "info") -> None:
        color = STATUS_COLORS.get(tone, STATUS_COLORS["info"])
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 9px;")
        self.status_label.setText(text)


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Metaword")
    app.setApplicationDisplayName("Metaword")
    app.setStyle("Fusion")
    app.setPalette(dark_palette())

    font = QFont()
    font.setFamilies(["Inter", "Segoe UI", "Ubuntu", "Noto Sans"])
    font.setPointSize(10)
    app.setFont(font)

    window = MetadataWindow()
    window.show()
    sys.exit(app.exec())



