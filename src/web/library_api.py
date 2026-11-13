"""Install immutable 5.0.0 library and route-collection archives locally."""
import asyncio
from pathlib import Path
import shutil
import uuid

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile

BAD_NAME = '\\/:*?"<>|'


def mount_library(app, service):
    async def receive(request: Request, label: str):
        """Return (archive path, temporary directory to clean up)."""
        content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        key = uuid.uuid4().hex
        if content_type == "multipart/form-data":
            form = await request.form()
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                raise HTTPException(422, f"请选择要导入的{label} ZIP 文件。")
            filename = Path(upload.filename or "").name
            if (not filename or filename != (upload.filename or "")
                    or any(c in filename for c in BAD_NAME)
                    or not filename.lower().endswith(".zip")):
                raise HTTPException(422, f"请选择有效的{label} ZIP 文件。")
            temporary = service.plugins.directory / "incoming" / key
            try:
                temporary.mkdir(parents=True)
                target = temporary / filename
                size = 0
                with target.open("wb") as output:
                    while True:
                        chunk = await upload.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if service.settings.max_upload is not None and size > service.settings.max_upload:
                            raise HTTPException(413, "文件超过已配置的上传上限。")
                        output.write(chunk)
                if not size:
                    raise HTTPException(422, "文件为空。")
                return target, temporary
            except BaseException:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        if content_type == "application/json":
            try:
                payload = await request.json()
            except ValueError as exc:
                raise HTTPException(422, "请求不是有效的 JSON。") from exc
            raw = payload.get("path") if isinstance(payload, dict) else None
            if not isinstance(raw, str) or not raw.strip():
                raise HTTPException(422, "请提供 ZIP 文件路径。")
            source = Path(raw).expanduser()
            if not source.is_file():
                raise HTTPException(404, f"文件不存在：{source}")
            return source, None
        raise HTTPException(
            415, '请使用 multipart/form-data 上传文件，或发送 {"path": "..."} 的 JSON 请求。'
        )

    @app.post("/api/libraries/install")
    async def install_library_route(request: Request):
        from operon.library_install import LegacyLibrary, install_library
        path, temporary = await receive(request, "算子库")
        try:
            try:
                result = await asyncio.to_thread(install_library, service.plugins, path)
            except LegacyLibrary as exc:
                raise HTTPException(400, str(exc)) from exc
            except (OSError, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
            await asyncio.to_thread(service.refresh_catalog)
            return result
        finally:
            if temporary is not None:
                shutil.rmtree(temporary, ignore_errors=True)

    @app.post("/api/routes/import-collection")
    async def import_collection_route(request: Request):
        from operon.library_install import RoutePinMismatch, install_routes_collection
        path, temporary = await receive(request, "路线包")
        try:
            try:
                return await asyncio.to_thread(install_routes_collection, service, path)
            except (KeyError, OSError, RoutePinMismatch, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            if temporary is not None:
                shutil.rmtree(temporary, ignore_errors=True)
