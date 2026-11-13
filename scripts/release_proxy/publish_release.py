#!/usr/bin/env python3
"""Publish GitHub release assets through the authenticated relay proxy.

The release workstation reaches GitHub only through the internal relay host, so
every API and upload request is sent over an HTTPS CONNECT tunnel instead of a
direct socket.  The GitHub token is read from a local file and never leaves the
workstation.

Typical use:

    python publish_release.py verify
    python publish_release.py selftest --size-mb 16
    python publish_release.py publish --tag v4.2.3 --name "..." \
        --body-file notes.md --assets D:/OperonTemp/release

Standard library only so the script runs with the stock Windows Python.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse
from pathlib import Path

API_HOST = "api.github.com"
UPLOAD_HOST = "uploads.github.com"
DEFAULT_REPO = "lovegavin/Operon"
DEFAULT_TIMEOUT = 120.0
DEFAULT_UPLOAD_TIMEOUT = 1800.0
CHUNK = 1 << 20


class ConfigError(Exception):
    pass


class GithubError(Exception):
    def __init__(self, status: int, message: str, body: bytes = b""):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message
        self.body = body


class RetryableError(Exception):
    pass


class Proxy:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password

    @classmethod
    def from_url(cls, value: str) -> "Proxy":
        parsed = urllib.parse.urlsplit(value if "://" in value else "http://" + value)
        if not parsed.hostname:
            raise ConfigError(f"proxy URL has no host: {value}")
        return cls(
            parsed.hostname,
            parsed.port or 18080,
            urllib.parse.unquote(parsed.username or ""),
            urllib.parse.unquote(parsed.password or ""),
        )

    @classmethod
    def load(cls, path: str | None = None) -> "Proxy":
        if path:
            candidate = Path(path).expanduser()
            if not candidate.exists():
                raise ConfigError(f"proxy config not found: {candidate}")
            return cls._from_file(candidate)
        environment = os.environ.get("OPERON_GH_PROXY")
        if environment:
            return cls.from_url(environment)
        home = Path(os.environ.get("USERPROFILE") or Path.home())
        candidate = home / ".operon" / "github_proxy.json"
        if candidate.exists():
            return cls._from_file(candidate)
        raise ConfigError(
            "no proxy configured; run scripts/release_proxy/proxy.ps1 -Action deploy "
            f"or pass --proxy-file (expected {candidate})"
        )

    @classmethod
    def _from_file(cls, path: Path) -> "Proxy":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot read proxy config {path}: {exc}") from exc
        if "url" in data and "host" not in data:
            return cls.from_url(str(data["url"]))
        try:
            return cls(
                str(data["host"]),
                int(data["port"]),
                str(data["username"]),
                str(data["password"]),
            )
        except (KeyError, ValueError) as exc:
            raise ConfigError(f"proxy config {path} is incomplete: {exc}") from exc

    @property
    def url(self) -> str:
        user = urllib.parse.quote(self.username, safe="")
        password = urllib.parse.quote(self.password, safe="")
        return f"http://{user}:{password}@{self.host}:{self.port}"

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


class TunnelConnection(http.client.HTTPSConnection):
    """HTTPS connection whose TCP leg is an authenticated proxy tunnel."""

    def __init__(self, host: str, proxy: Proxy, timeout: float):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._proxy = proxy

    def connect(self) -> None:
        raw = socket.create_connection((self._proxy.host, self._proxy.port), self.timeout)
        raw.settimeout(self.timeout)
        try:
            credentials = base64.b64encode(
                f"{self._proxy.username}:{self._proxy.password}".encode("utf-8")
            ).decode("ascii")
            request = (
                f"CONNECT {self.host}:{self.port} HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                f"Proxy-Authorization: Basic {credentials}\r\n"
                "Proxy-Connection: keep-alive\r\n\r\n"
            )
            raw.sendall(request.encode("ascii"))
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = raw.recv(4096)
                if not chunk:
                    raise OSError("proxy closed the connection during CONNECT")
                data += chunk
                if len(data) > 65536:
                    raise OSError("proxy response header is too large")
            status_line = data.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            fields = status_line.split()
            if len(fields) < 2 or fields[1] != "200":
                raise OSError(f"proxy refused CONNECT: {status_line}")
        except BaseException:
            raw.close()
            raise
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class ProgressReader:
    def __init__(self, stream, total: int, label: str, interval: float = 2.0):
        self.stream = stream
        self.total = total
        self.label = label
        self.interval = interval
        self.done = 0
        self.started = time.monotonic()
        self.last = 0.0

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.done += len(data)
        now = time.monotonic()
        if now - self.last >= self.interval or (not data and self.total):
            self.last = now
            elapsed = max(now - self.started, 0.001)
            rate = self.done / elapsed / (1024 * 1024)
            percent = (self.done * 100.0 / self.total) if self.total else 100.0
            sys.stderr.write(
                f"\r{self.label}: {self.done}/{self.total} bytes "
                f"({percent:5.1f}%) {rate:6.2f} MiB/s"
            )
            sys.stderr.flush()
        if not data and self.done:
            sys.stderr.write("\n")
            sys.stderr.flush()
        return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class Client:
    def __init__(self, token: str, proxy: Proxy | None, repo: str = DEFAULT_REPO):
        if not token:
            raise ConfigError("GitHub token is empty")
        self.token = token
        self.proxy = proxy
        self.repo = repo

    def _connection(self, host: str, timeout: float) -> http.client.HTTPSConnection:
        if self.proxy is None:
            return http.client.HTTPSConnection(
                host, 443, timeout=timeout, context=ssl.create_default_context()
            )
        return TunnelConnection(host, self.proxy, timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        host: str = API_HOST,
        payload: dict | None = None,
        body=None,
        length: int | None = None,
        headers: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> tuple[int, dict[str, str], bytes]:
        merged = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "operon-release-proxy/1.0",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            length = len(body)
            merged["Content-Type"] = "application/json"
        if length is not None:
            merged["Content-Length"] = str(length)
        merged.update(headers or {})
        connection = self._connection(host, timeout)
        connection.blocksize = CHUNK
        try:
            connection.request(method, path, body=body, headers=merged)
            response = connection.getresponse()
            data = response.read()
            return response.status, {name.lower(): value for name, value in response.getheaders()}, data
        except (OSError, http.client.HTTPException) as exc:
            raise RetryableError(f"{method} {host}{path}: {exc}") from exc
        finally:
            connection.close()

    @staticmethod
    def _message(data: bytes) -> str:
        try:
            parsed = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            return data[:300].decode("utf-8", "replace")
        if isinstance(parsed, dict):
            message = str(parsed.get("message", ""))
            errors = parsed.get("errors")
            if errors:
                message += f" ({errors})"
            return message or data[:300].decode("utf-8", "replace")
        return data[:300].decode("utf-8", "replace")

    def json(self, status: int, data: bytes, expected: tuple[int, ...]):
        if status not in expected:
            raise GithubError(status, self._message(data), data)
        if not data:
            return {}
        return json.loads(data)

    def get(self, path: str, expected: tuple[int, ...] = (200,), timeout: float = DEFAULT_TIMEOUT):
        status, headers, data = self.request("GET", path, timeout=timeout)
        return self.json(status, data, expected), headers

    def verify(self) -> dict:
        user, _ = self.get("/user")
        repository, _ = self.get(f"/repos/{self.repo}")
        rate, _ = self.get("/rate_limit")
        return {
            "login": user.get("login"),
            "scopes": "unknown",
            "can_push": bool(repository.get("permissions", {}).get("push")),
            "private": bool(repository.get("private")),
            "default_branch": repository.get("default_branch"),
            "rate_remaining": rate.get("resources", {}).get("core", {}).get("remaining"),
            "proxy": str(self.proxy) if self.proxy else "direct",
        }

    def list_releases(self, limit: int = 10) -> list[dict]:
        data, _ = self.get(f"/repos/{self.repo}/releases?per_page={limit}")
        return data

    def release_by_tag(self, tag: str) -> dict | None:
        status, _headers, data = self.request("GET", f"/repos/{self.repo}/releases/tags/{urllib.parse.quote(tag)}")
        if status == 404:
            return None
        return self.json(status, data, (200,))

    def create_release(
        self,
        tag: str,
        name: str,
        body: str,
        *,
        draft: bool = False,
        prerelease: bool = False,
        target: str | None = None,
    ) -> dict:
        payload: dict = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }
        if target:
            payload["target_commitish"] = target
        status, _headers, data = self.request("POST", f"/repos/{self.repo}/releases", payload=payload)
        if status == 422:
            existing = self.release_by_tag(tag)
            if existing is not None:
                print(f"release {tag} already exists: id={existing['id']}", file=sys.stderr)
                return existing
        return self.json(status, data, (201,))

    def delete_release(self, release_id: int) -> None:
        status, _headers, data = self.request("DELETE", f"/repos/{self.repo}/releases/{release_id}")
        if status not in (204, 200):
            raise GithubError(status, self._message(data), data)

    def assets(self, release_id: int) -> list[dict]:
        data, _ = self.get(f"/repos/{self.repo}/releases/{release_id}/assets?per_page=100")
        return data

    def delete_asset(self, asset_id: int) -> None:
        status, _headers, data = self.request("DELETE", f"/repos/{self.repo}/releases/assets/{asset_id}")
        if status not in (204, 200):
            raise GithubError(status, self._message(data), data)

    def delete_asset_by_name(self, release_id: int, name: str) -> None:
        for asset in self.assets(release_id):
            if asset.get("name") == name:
                print(f"removing previous asset {name} (id={asset['id']})", file=sys.stderr)
                self.delete_asset(int(asset["id"]))

    def check_asset(self, asset: dict, name: str, size: int, digest: str) -> dict:
        if asset.get("name") != name:
            raise GithubError(0, f"uploaded asset name mismatch: {asset.get('name')!r} != {name!r}")
        if int(asset.get("size", -1)) != size:
            raise GithubError(0, f"uploaded size mismatch for {name}: {asset.get('size')} != {size}")
        remote = asset.get("digest")
        if remote:
            expected = f"sha256:{digest}"
            if remote != expected:
                raise GithubError(0, f"uploaded digest mismatch for {name}: {remote} != {expected}")
        asset["local_sha256"] = digest
        return asset

    def upload(self, release_id: int, path: Path, name: str | None = None, attempts: int = 3) -> dict:
        path = Path(path)
        name = name or path.name
        if not re.fullmatch(r"[A-Za-z0-9._+-]+", name):
            raise ConfigError(f"asset name contains unsupported characters: {name!r}")
        size = path.stat().st_size
        digest = sha256_file(path)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                try:
                    self.delete_asset_by_name(release_id, name)
                except (GithubError, RetryableError) as exc:
                    print(f"could not remove stale asset {name}: {exc}", file=sys.stderr)
            try:
                print(f"uploading {name} ({size} bytes, sha256 {digest[:16]}...)", file=sys.stderr)
                with path.open("rb") as stream:
                    reader = ProgressReader(stream, size, f"{name} [{attempt}/{attempts}]")
                    status, _headers, data = self.request(
                        "POST",
                        f"/repos/{self.repo}/releases/{release_id}/assets?name={urllib.parse.quote(name)}",
                        host=UPLOAD_HOST,
                        body=reader,
                        length=size,
                        headers={"Content-Type": "application/octet-stream"},
                        timeout=DEFAULT_UPLOAD_TIMEOUT,
                    )
                if status in (201, 202):
                    asset = self.json(status, data, (201, 202))
                    return self.check_asset(asset, name, size, digest)
                if status == 429 or 500 <= status < 600:
                    raise RetryableError(f"HTTP {status}: {self._message(data)}")
                raise GithubError(status, self._message(data), data)
            except (RetryableError, OSError, http.client.HTTPException) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                wait = min(60, 5 * attempt)
                print(f"attempt {attempt} failed: {exc}; retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise SystemExit(f"upload failed for {name}: {last_error}")

    def download_digest(self, asset: dict) -> str:
        host = "api.github.com"
        parsed = urllib.parse.urlsplit(asset["url"])
        host = parsed.hostname or host
        path = parsed.path
        connection = self._connection(host, DEFAULT_UPLOAD_TIMEOUT)
        connection.blocksize = CHUNK
        digest = hashlib.sha256()
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/octet-stream",
                    "User-Agent": "operon-release-proxy/1.0",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise GithubError(response.status, response.read()[:300].decode("utf-8", "replace"))
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            connection.close()
        return digest.hexdigest()


def read_token(path: str | None) -> str:
    environment = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if path:
        candidate = Path(path).expanduser()
        if not candidate.exists():
            raise ConfigError(f"token file not found: {candidate}")
        token = candidate.read_text(encoding="utf-8").strip()
        if not token:
            raise ConfigError(f"token file is empty: {candidate}")
        return token
    if environment:
        return environment.strip()
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidate = home / ".operon" / "gh_token.txt"
    if candidate.exists():
        token = candidate.read_text(encoding="utf-8").strip()
        if token:
            return token
    raise ConfigError(
        "no GitHub token; set GH_TOKEN, pass --token-file, or create "
        f"{candidate}"
    )


def collect_assets(values: list[str]) -> list[Path]:
    assets: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_dir():
            assets.extend(sorted(item for item in path.iterdir() if item.is_file()))
        elif path.is_file():
            assets.append(path)
        else:
            raise ConfigError(f"asset path does not exist: {path}")
    unique: dict[str, Path] = {}
    for asset in assets:
        unique[asset.name] = asset
    return list(unique.values())


def command_verify(client: Client, arguments) -> int:
    summary = client.verify()
    print(json.dumps(summary, indent=2))
    if not summary["can_push"]:
        print(f"token cannot push to {client.repo}", file=sys.stderr)
        return 1
    return 0


def command_list(client: Client, arguments) -> int:
    for release in client.list_releases(20):
        print(f"{release.get('tag_name'):<24} id={release.get('id'):<10} draft={release.get('draft')} assets={len(release.get('assets', []))}")
    return 0


def command_create(client: Client, arguments) -> int:
    body = Path(arguments.body_file).read_text(encoding="utf-8") if arguments.body_file else ""
    release = client.create_release(
        arguments.tag,
        arguments.name or arguments.tag,
        body,
        draft=arguments.draft,
        prerelease=arguments.prerelease,
        target=arguments.target,
    )
    print(json.dumps({"id": release["id"], "tag": release["tag_name"], "url": release.get("html_url")}, indent=2))
    return 0


def command_upload(client: Client, arguments) -> int:
    assets = collect_assets(arguments.assets)
    if not assets:
        raise ConfigError("no assets selected")
    uploaded = []
    for asset in assets:
        uploaded.append(client.upload(arguments.release_id, asset))
    print(json.dumps([{ "name": item["name"], "size": item["size"], "digest": item.get("digest")} for item in uploaded], indent=2))
    return 0


def command_publish(client: Client, arguments) -> int:
    body = Path(arguments.body_file).read_text(encoding="utf-8") if arguments.body_file else ""
    release = client.create_release(
        arguments.tag,
        arguments.name or arguments.tag,
        body,
        draft=arguments.draft,
        prerelease=arguments.prerelease,
        target=arguments.target,
    )
    assets = collect_assets(arguments.assets)
    if not assets:
        raise ConfigError("no assets selected")
    uploaded = [client.upload(int(release["id"]), asset) for asset in assets]
    print(
        json.dumps(
            {
                "release_id": release["id"],
                "tag": release["tag_name"],
                "url": release.get("html_url"),
                "assets": [
                    {"name": item["name"], "size": item["size"], "digest": item.get("digest")}
                    for item in uploaded
                ],
            },
            indent=2,
        )
    )
    return 0


def command_check(client: Client, arguments) -> int:
    local = {path.name: path for path in collect_assets(arguments.assets)}
    remote = {asset["name"]: asset for asset in client.assets(arguments.release_id)}
    failures = 0
    for name, path in sorted(local.items()):
        asset = remote.get(name)
        if asset is None:
            print(f"MISSING  {name}")
            failures += 1
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        remote_size = int(asset.get("size", -1))
        remote_digest = asset.get("digest")
        ok = remote_size == size and (remote_digest is None or remote_digest == f"sha256:{digest}")
        print(
            f"{'OK      ' if ok else 'MISMATCH'} {name} local={size}/{digest[:16]} "
            f"remote={remote_size}/{(remote_digest or 'n/a')[:26]}"
        )
        failures += 0 if ok else 1
    for name in sorted(set(remote) - set(local)):
        print(f"EXTRA    {name}")
    print(f"{len(local) - failures}/{len(local)} assets verified")
    return 0 if failures == 0 else 1


def command_selftest(client: Client, arguments) -> int:
    tag = f"proxy-selftest-{int(time.time())}"
    release = client.create_release(
        tag,
        "Proxy connectivity self test",
        "Temporary release created by publish_release.py selftest; it is deleted automatically.",
        draft=True,
    )
    release_id = int(release["id"])
    temp = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    size = max(1, arguments.size_mb) * 1024 * 1024
    path = temp / f"{tag}.bin"
    try:
        with path.open("wb") as stream:
            remaining = size
            while remaining > 0:
                chunk = os.urandom(min(CHUNK, remaining))
                stream.write(chunk)
                remaining -= len(chunk)
        print(f"self test asset: {path} ({size} bytes)", file=sys.stderr)
        asset = client.upload(release_id, path)
        remote_digest = asset.get("digest")
        local_digest = asset["local_sha256"]
        if not remote_digest:
            remote_digest = f"sha256:{client.download_digest(asset)}"
        if remote_digest != f"sha256:{local_digest}":
            raise SystemExit(f"self test digest mismatch: {remote_digest} != sha256:{local_digest}")
        print(
            json.dumps(
                {
                    "ok": True,
                    "release_id": release_id,
                    "asset": asset["name"],
                    "size": asset["size"],
                    "digest": remote_digest,
                    "proxy": str(client.proxy) if client.proxy else "direct",
                },
                indent=2,
            )
        )
        return 0
    finally:
        try:
            client.delete_release(release_id)
            print(f"deleted temporary release {release_id}", file=sys.stderr)
        except (GithubError, RetryableError) as exc:
            print(f"warning: could not delete temporary release {release_id}: {exc}", file=sys.stderr)
        path.unlink(missing_ok=True)


def command_delete_release(client: Client, arguments) -> int:
    if not arguments.yes:
        raise SystemExit("refusing to delete a release without --yes")
    client.delete_release(arguments.release_id)
    print(f"deleted release {arguments.release_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish GitHub release assets through the relay proxy")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--token-file", help="default: %%USERPROFILE%%\\.operon\\gh_token.txt")
    parser.add_argument("--proxy-file", help="default: %%USERPROFILE%%\\.operon\\github_proxy.json")
    parser.add_argument("--direct", action="store_true", help="bypass the proxy (only when GitHub is reachable)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="show token identity, scopes and repository permissions")
    sub.add_parser("list", help="list recent releases")

    create = sub.add_parser("create", help="create a release without uploading assets")
    create.add_argument("--tag", required=True)
    create.add_argument("--name")
    create.add_argument("--body-file")
    create.add_argument("--target")
    create.add_argument("--draft", action="store_true")
    create.add_argument("--prerelease", action="store_true")

    upload = sub.add_parser("upload", help="upload assets to an existing release")
    upload.add_argument("--release-id", type=int, required=True)
    upload.add_argument("assets", nargs="+")

    publish = sub.add_parser("publish", help="create the release if needed and upload every asset")
    publish.add_argument("--tag", required=True)
    publish.add_argument("--name")
    publish.add_argument("--body-file")
    publish.add_argument("--target")
    publish.add_argument("--draft", action="store_true")
    publish.add_argument("--prerelease", action="store_true")
    publish.add_argument("--assets", nargs="+", required=True)

    check = sub.add_parser("check", help="compare local assets with an existing release")
    check.add_argument("--release-id", type=int, required=True)
    check.add_argument("--assets", nargs="+", required=True)

    selftest = sub.add_parser("selftest", help="draft release + upload + digest check + cleanup")
    selftest.add_argument("--size-mb", type=int, default=8)

    delete = sub.add_parser("delete-release", help="delete one release (cleanup only)")
    delete.add_argument("--release-id", type=int, required=True)
    delete.add_argument("--yes", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        token = read_token(arguments.token_file)
        proxy = None if arguments.direct else Proxy.load(arguments.proxy_file)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    client = Client(token, proxy, arguments.repo)
    handlers = {
        "verify": command_verify,
        "list": lambda c, a: command_list(c),
        "create": command_create,
        "upload": command_upload,
        "publish": command_publish,
        "check": command_check,
        "selftest": command_selftest,
        "delete-release": command_delete_release,
    }
    try:
        return handlers[arguments.command](client, arguments)
    except GithubError as exc:
        print(f"GitHub error: {exc}", file=sys.stderr)
        return 1
    except RetryableError as exc:
        print(f"network error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
