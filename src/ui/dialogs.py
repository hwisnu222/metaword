"""Frameless dialogs for previewing and editing metadata."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.metadata import first_metadata_value, metadata_edit_values, write_metadata_values
from ui.styles.theme import dark_palette, load_stylesheet


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
        self.setStyleSheet(load_stylesheet())
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
