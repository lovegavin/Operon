"""Test-only stand-in for scripts/desktop_server.py.

This fixture never executes science. It speaks only the host handshake used by
the native lifecycle tests: wait for `start`, publish the profile receipt, print
OPERON_READY, expose the three authenticated bootstrap endpoints, and honor
`shutdown` unless the mode explicitly ignores it. Behaviour is selected by a
`mode.txt` file copied next to this script by the Rust test.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_FILE = HERE / "mode.txt"


def read_mode() -> str:
    try:
        return MODE_FILE.read_text(encoding="utf-8").strip() or "normal"
    except FileNotFoundError:
        return "normal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--resolve-profile", action="store_true")
    parser.add_argument("--frontend", type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--wait-for-host", action="store_true")
    args, _unknown = parser.parse_known_args()
    return args


def spawn_breakaway_helper() -> None:
    helper = HERE / "unrelated_server.py"
    port_file = HERE / "breakaway_port.txt"
    error_file = HERE / "breakaway_error.txt"
    try:
        subprocess.Popen(
            [sys.executable, str(helper), "--port-file", str(port_file)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            # CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS
            creationflags=0x01000000 | 0x00000008,
        )
    except Exception as error:  # pragma: no cover - Windows-only fixture path
        error_file.write_text(repr(error), encoding="utf-8")
        print(f"breakaway spawn failed: {error!r}", file=sys.stderr, flush=True)
        raise SystemExit(9)


def main() -> int:
    mode = read_mode()
    args = parse_args()

    if args.profile_dir is not None:
        profile = Path(args.profile_dir).resolve()
        workspace = profile / "workspace"
        data_dir = workspace / ".studio"
    elif args.workspace is not None:
        workspace = Path(args.workspace).resolve()
        data_dir = workspace / ".studio"
        profile = workspace
    else:
        profile = (HERE / ".." / "profile").resolve()
        workspace = profile / "workspace"
        data_dir = workspace / ".studio"
    data_dir.mkdir(parents=True, exist_ok=True)

    # The host always attaches the job before writing this line.
    line = sys.stdin.readline()
    if line.strip() != "start":
        print("fixture did not receive the start handshake", file=sys.stderr, flush=True)
        return 3

    if mode == "crash":
        print("fixture crashed before readiness", file=sys.stderr, flush=True)
        return 7
    if mode == "delayed":
        time.sleep(1.0)
    if mode == "breakaway":
        spawn_breakaway_helper()

    instance_id = uuid.uuid4().hex
    secret = secrets.token_urlsafe(32)
    studio_token = "fixture-studio-" + uuid.uuid4().hex
    identity_id = "different-instance" if mode == "wrong_identity" else instance_id
    studio_version = "5.2.0" if mode == "wrong_version" else "5.3.0"

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
            if path == "/api/agent/identity":
                if self.headers.get("x-operon-bridge") != secret:
                    self._send(403, {"message": "bad discovery credential"})
                    return
                self._send(200, {"instance_id": identity_id})
                return
            if path == "/ready":
                self._send(200, {"status": "ok", "studio": studio_version})
                return
            if path == "/api/bootstrap":
                self._send(
                    200,
                    {
                        "token": studio_token,
                        "storage": {
                            "profile_dir": str(profile),
                            "workspace": str(workspace),
                            "data_dir": str(data_dir),
                            "registry": str(data_dir / "workflows" / "registry.json"),
                        },
                    },
                )
                return
            self._send(404, {"message": "not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    port = server.server_address[1]

    # The real service publishes its receipt from the FastAPI lifespan before
    # announcing readiness; preserve that ordering.
    if mode != "no_receipt":
        receipt_dir = data_dir / "agent" / "servers"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "protocol_version": 1,
            "instance_id": instance_id,
            "url": f"http://127.0.0.1:{port}",
            "pid": os.getpid(),
            "created": time.time(),
            "secret": secret,
            "headless": False,
            "api_version": 1,
        }
        (receipt_dir / f"{instance_id}.json").write_text(
            json.dumps(receipt), encoding="utf-8"
        )
        try:
            os.chmod(receipt_dir / f"{instance_id}.json", 0o600)
        except OSError:
            pass

    announced_pid = os.getpid() + 1 if mode == "wrong_pid" else os.getpid()
    print(
        "OPERON_READY "
        + json.dumps({"url": f"http://127.0.0.1:{port}", "pid": announced_pid}),
        flush=True,
    )

    if mode != "shutdown_ignore":
        def watch_host() -> None:
            try:
                for command in sys.stdin:
                    if command.strip() == "shutdown":
                        break
            finally:
                threading.Thread(target=server.shutdown, daemon=True).start()

        threading.Thread(target=watch_host, daemon=True).start()

    # Keep a failed test from leaking a fixture forever.
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
