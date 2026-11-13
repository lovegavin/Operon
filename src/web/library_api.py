"""Install immutable 5.0.0 library and route-collection archives locally."""
import asyncio
from pathlib import Path
import shutil
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

BAD_NAME = '\\/:*?"<>|'


def mount_library(app, service):
    async def receive(request: Request, label: str):
        """Return (archive path, temporary directory to clean up)."""
        content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        key = uuid.uuid4().hex
        name = None
        if content_type == "multipart/form-data":
            form = await request.form()
            raw_name = form.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                name = raw_name.strip()
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
                return target, temporary, name
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
            raw_name = payload.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                name = raw_name.strip()
            return source, None, name
        raise HTTPException(
            415, '请使用 multipart/form-data 上传文件，或发送 {"path": "..."} 的 JSON 请求。'
        )

    @app.get("/api/libraries")
    async def list_libraries_route():
        from operon.library_install import libraries_view
        return await asyncio.to_thread(libraries_view, service.plugins)

    @app.post("/api/libraries/install")
    async def install_library_route(request: Request):
        from operon.library_install import LegacyLibrary, LibraryConflict, install_library
        path, temporary, name = await receive(request, "算子库")
        try:
            try:
                result = await asyncio.to_thread(
                    install_library, service.plugins, path, name=name
                )
            except LegacyLibrary as exc:
                raise HTTPException(400, str(exc)) from exc
            except LibraryConflict as exc:
                return JSONResponse(status_code=409, content={"error": {
                    "code": "library_conflict",
                    "message": str(exc),
                    "conflicts": exc.conflicts,
                }})
            except (OSError, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
            await asyncio.to_thread(service.refresh_catalog)
            return result
        finally:
            if temporary is not None:
                shutil.rmtree(temporary, ignore_errors=True)

    @app.delete("/api/libraries/{name}")
    async def remove_library_route(name: str):
        from operon.library_install import uninstall_library
        try:
            result = await asyncio.to_thread(uninstall_library, service.plugins, name)
        except ValueError as exc:
            return JSONResponse(status_code=404, content={"error": {
                "code": "library_missing",
                "message": str(exc),
            }})
        await asyncio.to_thread(service.refresh_catalog)
        return result

    @app.post("/api/routes/import-collection")
    async def import_collection_route(request: Request):
        from operon.library_install import RoutePinMismatch, install_routes_collection
        path, temporary, _name = await receive(request, "路线包")
        try:
            try:
                return await asyncio.to_thread(install_routes_collection, service, path)
            except (KeyError, OSError, RoutePinMismatch, ValueError) as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            if temporary is not None:
                shutil.rmtree(temporary, ignore_errors=True)
