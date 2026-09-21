#!/usr/bin/env python3
"""Local Foil page + OpenRouter sidecar. Python standard library only."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

from runner import OpenRouter, Session
from runtime import Native, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wisp", default=os.environ.get("WISP", shutil.which("wisp")))
    parser.add_argument("--runtime", type=Path, default=Path.home() / ".local/state/shrine-agent")
    parser.add_argument("--seed-snapshot", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--resume", action="store_true", help="Replay recorded native operations and restore the saved conversation")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--budget", type=float, default=2.0, help="OpenRouter process cost cap, USD")
    args = parser.parse_args()
    if not args.wisp:
        parser.error("Provide --wisp or set WISP to the built Wisp binary")
    if not 0 < args.budget <= 100:
        parser.error("Choose a budget in (0, 100] USD")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if args.key_file:
        if args.key_file.stat().st_mode & 0o077:
            parser.error("The key file must be private (chmod 600)")
        key = args.key_file.read_text().strip()
    if not key:
        parser.error("Set OPENROUTER_API_KEY or provide --key-file")
    print("Compiling the Foil app and starting Shrine…", flush=True)
    native = Native(args.wisp, args.runtime, args.seed_snapshot)
    session = Session(native, OpenRouter(key, args.budget), args.runtime / "sessions", resume=args.resume)
    page = native.page().encode("utf-8")
    assets = Path(__file__).parent / "web"
    origin = f"http://127.0.0.1:{args.port}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, value, content_type="application/json"):
            data = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass

        def local_request(self):
            # No cross-origin mutation or DNS-rebinding access to paid calls.
            return (self.headers.get("Host") in {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
                    and self.headers.get("Origin", origin) in {origin, f"http://localhost:{args.port}"})

        def do_GET(self):
            if not self.local_request():
                return self.send(403, {"error": "Local origin required"})
            path = urlsplit(self.path).path
            if path == "/":
                self.send(200, page, "text/html; charset=utf-8")
            elif path in {"/api/state", "/api/export"}:
                data = session.snapshot()
                if path == "/api/state":
                    data.pop("messages", None)
                    data["chats"] = session.chats()
                self.send(200, data)
            elif path in {"/assets/app.js", "/assets/style.css"}:
                name = path.rsplit("/", 1)[-1]
                ctype = "text/javascript" if name.endswith(".js") else "text/css"
                self.send(200, (assets / name).read_bytes(), ctype + "; charset=utf-8")
            else:
                self.send(404, {"error": "Not found"})

        def do_POST(self):
            if not self.local_request() or self.headers.get("Content-Type") != "application/json":
                return self.send(403, {"error": "Local JSON request required"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 256_000:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Expected an object")
                action = self.path.removeprefix("/api/")
                if action not in {"turn", "goal", "new_chat", "switch_chat", "approve_compression", "dismiss_compression"}:
                    return self.send(404, {"error": "Not found"})
                if action in {"turn", "goal", "approve_compression", "dismiss_compression"} and body.get("chat_id") != session.session_id:
                    raise ValueError("The active chat changed; review it before submitting")
                if action == "goal" and (not isinstance(body.get("description"), str) or not body["description"].strip()):
                    raise ValueError("Describe the goal")
                if action == "switch_chat" and (not isinstance(body.get("chat_id"), str) or not body["chat_id"].isdigit()):
                    raise ValueError("Choose a saved chat")
                if action in {"approve_compression", "dismiss_compression"}:
                    pending = session.pending_compression
                    if not pending or body.get("proposal_ref") != pending["ref"]:
                        raise ValueError("This proposal is no longer current; request a revised proposal")
                if action == "turn":
                    if "external" in body:
                        validate(body["external"])
                    elif not isinstance(body.get("prompt"), str) or not body["prompt"].strip():
                        raise ValueError("Enter a prompt")
                session.start(action, body)
                self.send(202, {"ok": True})
            except (ValueError, TypeError) as e:
                self.send(400, {"error": str(e)})

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        print(f"SHRINE_AGENT_READY {origin}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        native.close()


if __name__ == "__main__":
    main()
