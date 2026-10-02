from __future__ import annotations

import json
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO

from .messages import parse_message


class WebLogHandler(SimpleHTTPRequestHandler):
    writer: TextIO

    def do_POST(self) -> None:
        if self.path != "/api/message":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            envelope = parse_message(raw, pc_recv_time_s=time.monotonic(), transport="web")
            self.writer.write(envelope.to_json_line())
            self.writer.write("\n")
            self.writer.flush()
        except Exception as exc:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} - {format % args}")


def run_web_server(host: str, port: int, out_path: str, static_dir: str | None = None) -> None:
    project_root = Path(__file__).resolve().parents[3]
    web_root = Path(static_dir) if static_dir else project_root / "web"
    if not web_root.exists():
        raise FileNotFoundError(f"web directory not found: {web_root}")

    log_path = Path(out_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8") as writer:
        handler_class = partial(WebLogHandler, directory=str(web_root))
        WebLogHandler.writer = writer
        server = ThreadingHTTPServer((host, port), handler_class)
        print(f"Serving ESKF Reference Lab web app at http://{host}:{port}")
        print(f"Writing web messages to {log_path}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
