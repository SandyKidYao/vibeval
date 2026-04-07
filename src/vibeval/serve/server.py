"""HTTP server and request handler for vibeval serve."""

from __future__ import annotations

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config import Config
from .router import Router

STATIC_DIR = Path(__file__).parent / "static"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class VibevalHandler(BaseHTTPRequestHandler):
    """Dispatch requests to the router or serve static files."""

    router: Router  # set by start_server
    config: Config  # set by start_server

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    # ------------------------------------------------------------------

    def _handle(self, method: str) -> None:
        path = urlparse(self.path).path

        if path.startswith("/api/"):
            self._handle_api(method, path)
        elif method == "GET" and path.startswith("/static/"):
            self._serve_static(path)
        elif method == "GET":
            self._serve_file(STATIC_DIR / "index.html")
        else:
            self._json_response(404, {"error": "Not found"})

    def _handle_api(self, method: str, path: str) -> None:
        match = self.router.dispatch(method, path)
        if match is None:
            self._json_response(404, {"error": f"No route for {method} {path}"})
            return

        handler, params = match

        body: Any = None
        if method in ("POST", "PUT"):
            body = self._read_json_body()
            if body is None and method == "POST":
                self._json_response(400, {"error": "Invalid or missing JSON body"})
                return

        try:
            status, data = handler(self.config, params, body)
            self._json_response(status, {"data": data} if status < 400 else data)
        except FileNotFoundError as e:
            self._json_response(404, {"error": str(e)})
        except ValueError as e:
            self._json_response(400, {"error": str(e)})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _serve_static(self, path: str) -> None:
        """Serve a file from the static/ directory."""
        # Strip /static/ prefix and resolve against STATIC_DIR
        rel = path[len("/static/"):]
        # Prevent path traversal
        if ".." in rel or rel.startswith("/"):
            self._json_response(403, {"error": "Forbidden"})
            return
        self._serve_file(STATIC_DIR / rel)

    def _serve_file(self, file_path: Path) -> None:
        """Serve a single file from disk."""
        if not file_path.is_file():
            self._json_response(404, {"error": "Not found"})
            return

        content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Cache static assets (CSS/JS) but not index.html
        if file_path.name != "index.html":
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, status: int, data: Any) -> None:
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, format: str, *args: Any) -> None:
        # Quieter logging: only show method + path + status
        sys.stderr.write(f"  {args[0]}\n" if args else "")


def start_server(config: Config, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the vibeval web server (blocking)."""
    from .api import register_routes

    router = Router()
    register_routes(router)

    VibevalHandler.router = router
    VibevalHandler.config = config

    server = HTTPServer((host, port), VibevalHandler)
    print(f"vibeval dashboard running at http://{host}:{port}/")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
