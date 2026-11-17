"""Reusable widgets for the file list and frameless window chrome."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.files import GENERATABLE_EXTENSIONS, IMAGE_EXTENSIONS, human_size
from ui.styles.theme import PRIMARY, STATUS_COLORS


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
