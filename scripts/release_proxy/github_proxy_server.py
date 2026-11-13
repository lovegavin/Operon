#!/usr/bin/env python3
"""Authenticated HTTPS CONNECT proxy for GitHub release traffic.

The release workstation can reach the relay host but not GitHub directly, while
the relay host can reach GitHub.  This proxy terminates nothing: it only opens
an opaque CONNECT tunnel to an allow-listed host and port, so TLS stays end to
end between the workstation and GitHub.

Only CONNECT to allow-listed hosts on allow-listed ports is accepted, and every
request needs HTTP Basic proxy credentials.  That keeps the relay from becoming
a general-purpose open proxy on the shared network.

Standard library only: the relay is a shared login node without root access.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hmac
import json
import logging
import os
import secrets
import signal
import socket
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

CHUNK = 256 * 1024
MAX_HEADER = 64 * 1024
LOG = logging.getLogger("github-proxy")

DEFAULT_ALLOW_HOSTS = [
    # GitHub: API, releases, raw files and LFS.
    "github.com",
    "api.github.com",
    "uploads.github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "githubusercontent.com",
    "github-cloud.s3.amazonaws.com",
    # Python packages: upstream PyPI and the configured Tsinghua mirror.
    "pypi.org",
    "pythonhosted.org",
    "tuna.tsinghua.edu.cn",
    # Models and datasets.
    "huggingface.co",
    "hf.co",
    "hf-mirror.com",
    # Conda and micromamba.
    "anaconda.org",
    "anaconda.com",
    "mamba.pm",
    # Node packages and Node binaries.
    "npmjs.org",
    "npmmirror.com",
    "nodejs.org",
]


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, data: dict, base: Path):
        try:
            self.listen_host = str(data.get("listen_host", "0.0.0.0"))
            self.listen_port = int(data.get("listen_port", 18080))
            self.username = str(data["username"])
            self.password = str(data["password"])
        except KeyError as exc:
            raise ConfigError(f"missing config field: {exc}") from exc
        if not self.username or not self.password:
            raise ConfigError("username and password must not be empty")
        self.allow_hosts = [str(item).strip().lower().lstrip(".") for item in data.get("allow_hosts", DEFAULT_ALLOW_HOSTS)]
        self.allow_ports = {int(item) for item in data.get("allow_ports", [443])}
        self.max_connections = int(data.get("max_connections", 32))
        self.idle_timeout = float(data.get("idle_timeout", 900))
        self.connect_timeout = float(data.get("connect_timeout", 30))
        self.prefer_ipv4 = bool(data.get("prefer_ipv4", True))
        log_file = Path(str(data.get("log_file", "proxy.log")))
        self.log_file = log_file if log_file.is_absolute() else base / log_file


def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a JSON object: {path}")
    return Config(data, path.parent)


def init_config(path: Path, port: int) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing config: {path}")
    config = {
        "listen_host": "0.0.0.0",
        "listen_port": port,
        "username": "operon",
        "password": secrets.token_urlsafe(24),
        "allow_hosts": DEFAULT_ALLOW_HOSTS,
        "allow_ports": [443],
        "max_connections": 32,
        "idle_timeout": 900,
        "connect_timeout": 30,
        "prefer_ipv4": True,
        "log_file": "proxy.log",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
    print(f"created {path}")


def host_allowed(host: str, allowed: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for entry in allowed:
        if host == entry or host.endswith("." + entry):
            return True
    return False


def authorized(header: str | None, config: Config) -> bool:
    if not header:
        return False
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    expected = f"{config.username}:{config.password}"
    return hmac.compare_digest(decoded, expected)


async def respond(writer: asyncio.StreamWriter, status: str, message: str) -> None:
    body = message.encode("utf-8", "replace") + b"\n"
    head = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    writer.write(head + body)
    try:
        await writer.drain()
    except (ConnectionError, OSError):
        pass


def parse_head(raw: bytes) -> tuple[str, str, str, dict[str, str]]:
    lines = raw.split(b"\r\n")
    request = lines[0].decode("latin-1")
    parts = request.split()
    if len(parts) != 3:
        raise ValueError(f"malformed request line: {request!r}")
    method, target, version = parts
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        name, separator, value = line.partition(b":")
        if not separator:
            raise ValueError("malformed header line")
        headers[name.strip().lower().decode("latin-1")] = value.strip().decode("latin-1")
    return method, target, version, headers


async def pump(source: asyncio.StreamReader, sink: asyncio.StreamWriter, idle_timeout: float) -> int:
    total = 0
    while True:
        chunk = await asyncio.wait_for(source.read(CHUNK), idle_timeout)
        if not chunk:
            break
        sink.write(chunk)
        await sink.drain()
        total += len(chunk)
    try:
        sink.write_eof()
    except (OSError, RuntimeError):
        pass
    return total


async def open_upstream(host: str, port: int, config: Config):
    if not config.prefer_ipv4:
        return await asyncio.open_connection(host, port)
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM, family=socket.AF_INET)
    if not infos:
        raise OSError(f"no IPv4 address for {host}")
    last: OSError | None = None
    for _family, _type, _proto, _canon, sockaddr in infos:
        try:
            return await asyncio.open_connection(sockaddr[0], port)
        except OSError as exc:
            last = exc
    if last is not None:
        raise last
    raise OSError(f"cannot connect to {host}:{port}")


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, config: Config, slots: asyncio.Semaphore) -> None:
    peer = writer.get_extra_info("peername") or ("?", 0)
    client = str(peer[0])
    started = time.monotonic()
    target = "-"
    outcome = "closed"
    uploaded = 0
    downloaded = 0
    upstream: asyncio.StreamWriter | None = None
    try:
        async with slots:
            try:
                raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), config.connect_timeout)
            except asyncio.LimitOverrunError:
                outcome = "header-too-large"
                await respond(writer, "431 Request Header Fields Too Large", "request header exceeds 64 KiB")
                return
            except asyncio.IncompleteReadError:
                outcome = "client-closed-before-headers"
                return
            except asyncio.TimeoutError:
                outcome = "header-timeout"
                await respond(writer, "408 Request Timeout", "no request header within timeout")
                return

            if len(raw) > MAX_HEADER:
                outcome = "header-too-large"
                await respond(writer, "431 Request Header Fields Too Large", "request header exceeds 64 KiB")
                return

            try:
                method, target, _version, headers = parse_head(raw)
            except ValueError as exc:
                outcome = "malformed-request"
                await respond(writer, "400 Bad Request", str(exc))
                return

            if not authorized(headers.get("proxy-authorization"), config):
                outcome = "unauthorized"
                writer.write(
                    b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                    b'Proxy-Authenticate: Basic realm="operon-github", charset="UTF-8"\r\n'
                    b"Content-Length: 21\r\n"
                    b"Connection: close\r\n\r\n"
                    b"proxy authentication\n"
                )
                await writer.drain()
                return

            if method.upper() != "CONNECT":
                outcome = "method-not-allowed"
                await respond(writer, "405 Method Not Allowed", "this proxy only accepts CONNECT for HTTPS")
                return

            host, separator, port_text = target.rpartition(":")
            if not separator:
                host, port_text = target, "443"
            host = host.strip("[]")
            try:
                port = int(port_text)
            except ValueError:
                outcome = "bad-port"
                await respond(writer, "400 Bad Request", f"invalid CONNECT target: {target}")
                return
            if port not in config.allow_ports:
                outcome = "port-denied"
                await respond(writer, "403 Forbidden", f"port {port} is not allowed")
                return
            if not host_allowed(host, config.allow_hosts):
                outcome = "host-denied"
                await respond(writer, "403 Forbidden", f"host {host!r} is not allowed")
                return

            try:
                upstream_reader, upstream = await asyncio.wait_for(
                    open_upstream(host, port, config), config.connect_timeout
                )
            except (asyncio.TimeoutError, OSError) as exc:
                outcome = "upstream-failed"
                await respond(writer, "502 Bad Gateway", f"cannot reach {host}:{port}: {exc}")
                return

            writer.write(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: operon-github-proxy\r\n\r\n")
            await writer.drain()
            outcome = "tunnel"

            tasks = [
                asyncio.create_task(pump(reader, upstream, config.idle_timeout)),
                asyncio.create_task(pump(upstream_reader, writer, config.idle_timeout)),
            ]
            try:
                uploaded, downloaded = await asyncio.gather(*tasks)
            except asyncio.TimeoutError:
                outcome = "idle-timeout"
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except (ConnectionError, OSError) as exc:
                outcome = f"tunnel-error:{type(exc).__name__}"
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        outcome = "internal-error"
        LOG.exception("unhandled proxy error client=%s target=%s", client, target)
    finally:
        for stream in (upstream, writer):
            if stream is None:
                continue
            try:
                stream.close()
            except (OSError, RuntimeError):
                pass
        if upstream is not None:
            try:
                await upstream.wait_closed()
            except (OSError, RuntimeError):
                pass
        try:
            await writer.wait_closed()
        except (OSError, RuntimeError):
            pass
        LOG.info(
            "client=%s target=%s outcome=%s up=%d down=%d seconds=%.2f",
            client,
            target,
            outcome,
            uploaded,
            downloaded,
            time.monotonic() - started,
        )


def configure_logging(config: Config, verbose: bool) -> None:
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.setLevel(logging.DEBUG if verbose else logging.INFO)
    LOG.addHandler(handler)
    LOG.addHandler(console)
    LOG.propagate = False


async def serve(config: Config) -> None:
    slots = asyncio.Semaphore(config.max_connections)
    server = await asyncio.start_server(
        lambda reader, writer: handle(reader, writer, config, slots),
        config.listen_host,
        config.listen_port,
        reuse_address=True,
        limit=MAX_HEADER,
    )
    addresses = ", ".join(sorted({str(sock.getsockname()) for sock in server.sockets or []}))
    LOG.info(
        "listening on %s allow_hosts=%s allow_ports=%s max_connections=%d",
        addresses,
        ",".join(config.allow_hosts),
        ",".join(str(port) for port in sorted(config.allow_ports)),
        config.max_connections,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    async with server:
        await stop.wait()
    LOG.info("stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authenticated GitHub CONNECT proxy")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--pid-file", type=Path)
    parser.add_argument("--init-config", action="store_true", help="create a config with a random password and exit")
    parser.add_argument("--port", type=int, default=18080, help="port used by --init-config")
    parser.add_argument("--verbose", action="store_true")
    arguments = parser.parse_args(argv)

    if arguments.init_config:
        try:
            init_config(arguments.config, arguments.port)
        except OSError as exc:
            print(f"cannot create config: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        config = load_config(arguments.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    configure_logging(config, arguments.verbose)
    if arguments.pid_file:
        arguments.pid_file.parent.mkdir(parents=True, exist_ok=True)
        arguments.pid_file.write_text(f"{os.getpid()}\n", encoding="ascii")
    try:
        asyncio.run(serve(config))
    except KeyboardInterrupt:
        pass
    finally:
        if arguments.pid_file and arguments.pid_file.exists():
            arguments.pid_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
