"""Dark-mode metadata manager window built with PySide6.

Run it from the `src` directory with::

    python -m ui.window
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs import MetadataEditDialog, MetadataPreviewDialog
from ui.files import IMAGE_EXTENSIONS
from ui.styles.theme import STATUS_COLORS, dark_palette, load_stylesheet
from ui.widgets import FileRow, TitleBar, clear_icon
from ui.worker.metadata import AddMetadataWorker, CheckWorker, MetadataWorker


class MetadataWindow(QWidget):
    """Main window: lists the selected directory with per-file metadata actions."""

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
        self.setStyleSheet(load_stylesheet())
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
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.path_label.setToolTip(str(self.directory))
        heading.addWidget(self.path_label)
        header.addLayout(heading, 1)

        self.choose_button = QPushButton("Choose folder")
        self.choose_button.setObjectName("secondaryButton")
        self.choose_button.setCursor(Qt.PointingHandCursor)
        self.choose_button.setToolTip("Choose which folder to list")
        self.choose_button.clicked.connect(self._choose_directory)
        header.addWidget(self.choose_button, 0, Qt.AlignTop)

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
            ("Ctrl+O", self._choose_directory),
            ("F5", self.refresh),
            ("Ctrl+F", self.search_input.setFocus),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)

    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose folder", str(self.directory)
        )
        if not selected:
            return

        directory = Path(selected).resolve()
        if directory == self.directory:
            return

        self.directory = directory
        self.path_label.setText(str(directory))
        self.path_label.setToolTip(str(directory))
        self.search_input.clear()
        self.refresh()

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
        if path.parent != self.directory:
            return

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
    window.showMaximized()
    sys.exit(app.exec())
