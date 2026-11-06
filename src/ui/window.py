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
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
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
    """One file entry with a metadata check and an add-metadata action."""

    add_requested = Signal(object)
    check_toggled = Signal(object, bool)

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self.is_image = path.suffix.lower() in IMAGE_EXTENSIONS
        self.can_generate = path.suffix.lower() in GENERATABLE_EXTENSIONS
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


class MetadataWindow(QWidget):
    """Main window: lists the current directory with per-file metadata actions."""

    def __init__(self, directory: Path | None = None) -> None:
        super().__init__()
        self.directory = Path(directory or Path.cwd()).resolve()
        self._rows: list[FileRow] = []
        self._rows_by_path: dict[Path, FileRow] = {}
        self._check_workers: dict[Path, CheckWorker] = {}
        self._add_workers: dict[Path, AddMetadataWorker] = {}
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



