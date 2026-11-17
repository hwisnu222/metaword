"""Dark theme palette and QSS loader for the UI."""

from __future__ import annotations

from importlib.resources import files

from PySide6.QtGui import QColor, QPalette

PRIMARY = "#3B82F6"

STATUS_COLORS = {
    "info": "#60A5FA",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
    "muted": "#64748B",
}


def load_stylesheet() -> str:
    """Read the QSS shipped next to this module."""
    package = __name__.rsplit(".", 1)[0]
    return files(package).joinpath("style.qss").read_text(encoding="utf-8")


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
