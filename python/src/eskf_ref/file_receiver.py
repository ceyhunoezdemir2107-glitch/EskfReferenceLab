from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _safe_filename(name: str | None) -> str:
    if not name:
        return f"android_upload_{int(time.time() * 1000)}.jsonl.gz"
    safe = Path(name).name.strip()
    if not safe:
        return f"android_upload_{int(time.time() * 1000)}.jsonl.gz"
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in safe)


class UploadHandler(BaseHTTPRequestHandler):
    server: "UploadServer"

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/upload":
            self.send_error(404, "expected /upload")
            return

        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self.send_error(411, "Content-Length required")
            return

        try:
            remaining = int(length_header)
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return

        query = parse_qs(parsed.query)
        filename = _safe_filename(
            query.get("filename", [None])[0] or self.headers.get("X-Log-Filename")
        )
        target = self.server.out_dir / filename
        if target.exists():
            stem = target.stem
            suffix = "".join(target.suffixes)
            target = self.server.out_dir / f"{stem}_{int(time.time() * 1000)}{suffix}"
        temp = target.with_name(target.name + ".part")

        written = 0
        try:
            with temp.open("wb") as handle:
                while remaining > 0:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError("upload ended before Content-Length was reached")
                    handle.write(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
            os.replace(temp, target)
        except Exception as exc:
            if temp.exists():
                temp.unlink()
            self.send_error(500, f"upload failed: {exc}")
            return

        response = {
            "ok": True,
            "filename": target.name,
            "bytes": written,
            "path": str(target),
        }
        print(f"UPLOAD {target} {written} bytes", flush=True)
        body = json.dumps(response, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class UploadServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], out_dir: Path):
        super().__init__(server_address, UploadHandler)
        self.out_dir = out_dir


def run_file_receiver(host: str, port: int, out_dir: str) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    server = UploadServer((host, port), output)
    print(f"Receiving completed log uploads on http://{host}:{port}/upload", flush=True)
    print(f"Writing uploaded files to {output.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping upload receiver")
    finally:
        server.server_close()
