"""Import one route collection archive without extracting it to disk."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

MAX_MEMBERS = 200
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def _member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("路线压缩包包含不安全的路径。")
    return path


def _read_limited(archive: ZipFile, info) -> bytes:
    if info.flag_bits & 0x1:
        raise ValueError("路线压缩包不能包含加密文件。")
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("路线压缩包中的单个 .operon.zip 文件过大。")
    with archive.open(info) as stream:
        data = stream.read(MAX_MEMBER_BYTES + 1)
    if len(data) > MAX_MEMBER_BYTES:
        raise ValueError("路线压缩包中的单个 .operon.zip 文件过大。")
    return data


def route_members(data: bytes) -> list[tuple[str, bytes]]:
    """Return ``(filename, bundle_bytes)`` for routes below route/ or routes/."""
    try:
        archive = ZipFile(BytesIO(data))
    except BadZipFile as exc:
        raise ValueError("路线包不是有效的 zip 文件。") from exc
    with archive:
        members: list[tuple[str, bytes]] = []
        total = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = _member_path(info.filename)
            parents = {part.lower() for part in path.parts[:-1]}
            if not parents & {"route", "routes"}:
                continue
            if not path.name.lower().endswith(".operon.zip"):
                continue
            if len(members) >= MAX_MEMBERS:
                raise ValueError(f"路线包中的 .operon.zip 文件过多（最多 {MAX_MEMBERS} 个）。")
            content = _read_limited(archive, info)
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("路线压缩包解压后过大。")
            members.append((path.name, content))
    if not members:
        raise ValueError("路线包中没有 route/ 或 routes/ 下的 .operon.zip 文件。")
    return members
