"""File type and size helpers used by the file list."""

from __future__ import annotations

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


def human_size(size: int) -> str:
    """Return a compact, human readable file size."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
