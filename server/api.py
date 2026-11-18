"""HTTP API that lists the selected folder with metadata and thumbnails."""

from __future__ import annotations

import io
import json
import sys
from functools import lru_cache, partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import quote, unquote, urlsplit

from exiftool import ExifToolHelper
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from ui.files import IMAGE_EXTENSIONS
from ui.metadata import metadata_edit_values, split_metadata_list

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
THUMBNAIL_SIZE = (256, 256)


class ApiServer:
    """Serves the selected directory over HTTP on localhost."""

    def __init__(
        self,
        directory: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.directory = directory.resolve()
        self._lock = Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/api/files"

    def start(self) -> None:
        if self._httpd is not None:
            return

        handler = partial(_ApiHandler, api=self)
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        httpd.daemon_threads = True
        thread = Thread(
            target=httpd.serve_forever,
            kwargs={"poll_interval": 0.1},
            name="metaword-api",
            daemon=True,
        )
        self._httpd = httpd
        self._thread = thread
        thread.start()

    def set_directory(self, directory: Path) -> None:
        with self._lock:
            self.directory = directory.resolve()

    def stop(self) -> None:
        httpd = self._httpd
        thread = self._thread
        if httpd is None:
            return

        httpd.shutdown()
        httpd.server_close()
        if thread is not None:
            thread.join(timeout=2)
        self._httpd = None
        self._thread = None


class _ApiHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server, api: ApiServer) -> None:
        self.api = api
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/files":
            directory = self._current_directory()
            files = _list_files(directory)
            self._send_json(
                {
                    "directory": str(directory),
                    "count": len(files),
                    "files": files,
                }
            )
        elif path.startswith("/api/thumbnail/"):
            name = unquote(path.removeprefix("/api/thumbnail/"))
            self._send_thumbnail(name)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _current_directory(self) -> Path:
        with self.api._lock:
            return self.api.directory

    def _send_thumbnail(self, name: str) -> None:
        directory = self._current_directory()
        path = (directory / name).resolve()
        if path.parent != directory or not path.is_file():
            self._send_json({"error": "Thumbnail not found"}, 404)
            return

        try:
            content = _thumbnail(str(path), path.stat().st_mtime_ns)
        except (OSError, ValueError):
            content = None
        if content is None:
            self._send_json({"error": "Thumbnail unavailable"}, 404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        pass


def _list_files(directory: Path) -> list[dict[str, object]]:
    try:
        paths = [
            path
            for path in directory.iterdir()
            if path.is_file() and not path.name.startswith(".")
        ]
    except OSError:
        paths = []

    metadata = _read_metadata(paths)
    files: list[dict[str, object]] = []
    for path in sorted(paths, key=lambda item: item.name.casefold()):
        values = metadata.get(path, {})
        files.append(
            {
                "name": path.name,
                "title": values.get("title", ""),
                "description": values.get("description", ""),
                "keyword": split_metadata_list(values.get("keywords", "")),
                "category": split_metadata_list(values.get("categories", "")),
                "thumbnail": (
                    f"/api/thumbnail/{quote(path.name, safe='')}"
                    if path.suffix.lower() in IMAGE_EXTENSIONS
                    else None
                ),
            }
        )
    return files


def _read_metadata(paths: list[Path]) -> dict[Path, dict[str, str]]:
    if not paths:
        return {}

    try:
        with ExifToolHelper() as et:
            results = et.get_metadata([str(path) for path in paths])
    except Exception:
        return {}

    return {
        path: metadata_edit_values(result)
        for path, result in zip(paths, results)
        if isinstance(result, dict)
    }


@lru_cache(maxsize=128)
def _thumbnail(path: str, mtime_ns: int) -> bytes | None:
    with Image.open(path) as image:
        image.thumbnail(THUMBNAIL_SIZE)
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
    return buffer.getvalue()
