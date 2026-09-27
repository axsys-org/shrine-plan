"""Separate read-only inspector. No model, prompts, terminal or mutation proxy."""
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from client import Client

ASSETS = Path(__file__).with_name("viewer-web")


def handler(client, artifacts):
    artifacts = Path(artifacts)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path == "/api":
                    query = parse_qs(url.query)
                    method = query.get("method", ["status"])[0]
                    args = json.loads(query.get("args", ["{}"])[0])
                    if method not in {"status", "read", "context", "events"} or (method == "events" and any(k in args for k in ("consumer", "acknowledge"))):
                        raise ValueError("Inspector only permits reads")
                    data = json.dumps(client.call(method, **args)).encode()
                    kind = "application/json"
                elif url.path.startswith("/artifact/"):
                    key = url.path.rsplit("/", 1)[-1]
                    if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
                        raise ValueError("Expected content hash")
                    data = (artifacts / key).read_bytes()
                    if hashlib.sha256(data).hexdigest() != key:
                        raise ValueError("Artifact hash mismatch")
                    kind = "text/plain; charset=utf-8"
                else:
                    name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(url.path)
                    if not name:
                        self.send_error(404); return
                    data = (ASSETS / name).read_bytes()
                    kind = {"index.html": "text/html", "app.js": "application/javascript", "style.css": "text/css"}[name]
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
                self.end_headers(); self.wfile.write(data)
            except Exception as error:
                self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"error": str(error)}).encode())

        def do_POST(self):
            self.send_error(405, "Read-only inspector")

        def log_message(self, *args):
            pass

    return Handler


def serve(connection, port=8777):
    client = Client(connection)
    artifacts = Path(connection).resolve().parent / "artifacts"
    ThreadingHTTPServer(("127.0.0.1", port), handler(client, artifacts)).serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", required=True)
    p.add_argument("--port", type=int, default=8777)
    a = p.parse_args(); serve(a.connection, a.port)
