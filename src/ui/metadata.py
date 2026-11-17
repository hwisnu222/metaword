"""Read and write the metadata fields used by the UI."""

from __future__ import annotations

from pathlib import Path

from exiftool import ExifToolHelper


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
