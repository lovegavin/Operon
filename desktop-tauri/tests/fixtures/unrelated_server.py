"""Test-only loopback HTTP process used to prove an unrelated process survives.

It is also the helper that a job-attached fixture spawns with
CREATE_BREAKAWAY_FROM_JOB. It performs no product work and has no Operon imports.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # noqa: N802 - stdlib hook
        pass

    def _send(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib hook
        path = self.path.split("?", 1)[0]
        if path == "/stop":
            self._send(200, {"stopping": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._send(200, {"ok": True, "pid": os.getpid()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--port-file", type=Path)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    port = server.server_address[1]
    if args.port_file is not None:
        args.port_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.port_file.with_suffix(".tmp")
        temporary.write_text(str(port), encoding="utf-8")
        temporary.replace(args.port_file)
    else:
        print(port, flush=True)

    timer = threading.Timer(120, os._exit, args=(0,))
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever(poll_interval=0.05)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
