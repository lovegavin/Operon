"""Loopback agent gateway. CLI and MCP use exactly these canvas commands."""
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from operon.documents import CommandError, DocumentHub
from src.web.storage import atomic_json
from src.web.models import Graph
from src.web.graph import compile_graph


class Bridge:
    def __init__(self, app, service, studio_token):
        self.app, self.service, self.studio_token = app, service, studio_token
        self.hub = DocumentHub(service)
        self.id, self.secret = uuid.uuid4().hex, secrets.token_urlsafe(32)
        self.connections = {}
        self.path = service.directory / "agent/servers" / f"{self.id}.json"
        self.register_routes()

    def publish(self, url):
        if not url:
            return
        import psutil
        atomic_json(self.path, {"protocol_version": 1, "instance_id": self.id, "url": url,
                               "pid": os.getpid(), "created": psutil.Process().create_time(), "secret": self.secret,
                               "headless": bool(getattr(self.app.state, 'headless', False)), "api_version": 1})
        os.chmod(self.path, 0o600)

    def close(self):
        self.path.unlink(missing_ok=True)

    def actor(self, request, capability):
        if hmac.compare_digest(request.headers.get("x-studio-token", ""), self.studio_token):
            return "user"
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        value = self.connections.get(hashlib.sha256(token.encode()).hexdigest())
        if not value or capability not in value["scopes"]:
            if capability == 'plugins':
                guidance = ("Agent connection requires the 'plugins' capability. "
                            "Reconnect the MCP client with --allow-plugins to authorize operator "
                            "package changes and environment preparation; a data-independent "
                            "check-environment request only needs context permission.")
            else:
                guidance = f"Agent connection requires the '{capability}' capability."
            raise HTTPException(403, guidance)
        return "agent:" + value["name"]

    def register_routes(self):
        app, hub, service = self.app, self.hub, self.service

        @app.get("/api/agent/identity")
        def identity(request: Request):
            if not hmac.compare_digest(request.headers.get("x-operon-bridge", ""), self.secret):
                raise HTTPException(403, "Invalid instance discovery credential")
            return {"instance_id": self.id}

        @app.exception_handler(CommandError)
        async def command_error(request, error):
            return JSONResponse({"code": error.code, "message": str(error), "details": error.details}, status_code=error.status)

        @app.post("/api/agent/connect")
        def connect(request: Request, payload: dict):
            if not hmac.compare_digest(request.headers.get("x-operon-bridge", ""), self.secret):
                raise HTTPException(403, "Use the local instance discovery file to connect")
            scopes = payload.get("scopes", ["context", "edit"])
            if not isinstance(scopes, list) or not set(scopes) <= {"context", "edit", "run", "plugins"}:
                raise CommandError("invalid_scopes", "Unknown connection capabilities")
            token = secrets.token_urlsafe(32)
            key = hashlib.sha256(token.encode()).hexdigest()
            self.connections[key] = {"name": str(payload.get("name", "external-agent"))[:80], "scopes": scopes}
            return {"token": token, "scopes": scopes, "instance_id": self.id}

        @app.get("/api/agent/connections")
        def connections(request: Request):
            self.actor(request, "context")
            return [{"id": key, **value} for key, value in self.connections.items()]

        @app.post("/api/agent/disconnect")
        def disconnect(request: Request):
            self.actor(request, "context")
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            self.connections.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            return {"disconnected": True}

        @app.post("/api/agent/connections/revoke")
        def revoke(request: Request, payload: dict):
            if not hmac.compare_digest(request.headers.get("x-studio-token", ""), self.studio_token):
                raise HTTPException(403, "Only the desktop user can revoke another connection")
            self.connections.pop(payload.get("id"), None)
            return {"revoked": True}

        @app.post("/api/agent/connections/revoke-all")
        def revoke_all(request: Request):
            if not hmac.compare_digest(request.headers.get("x-studio-token", ""), self.studio_token):
                raise HTTPException(403, "Only the desktop user can revoke connections")
            revoked = len(self.connections)
            self.connections.clear()
            return {"revoked": revoked}

        @app.get("/api/agent/pool")
        def pool_status(request: Request):
            self.actor(request, "context")
            from operon import managed_pool
            return managed_pool.inspect_pool()

        @app.post("/api/agent/pool/stop")
        def pool_stop(request: Request, payload: dict | None = None):
            self.actor(request, "run")
            from operon import managed_pool
            try:
                return managed_pool.stop_pool(force=bool((payload or {}).get("force")))
            except managed_pool.PoolClientError as exc:
                raise HTTPException(409, str(exc)) from exc

        @app.get("/api/agent/remote")
        def remote_status(request: Request):
            self.actor(request, "context")
            return service.remotes.status()

        @app.get("/api/agent/remote/summary")
        def remote_summary(request: Request):
            self.actor(request, "context")
            return service.remotes.status(brief=True)

        @app.post("/api/agent/remote/{key}/ensure")
        def remote_ensure(key: str, request: Request, payload: dict | None = None):
            self.actor(request, "run")
            return service.remotes.ensure(key)

        @app.post("/api/agent/remote/{key}/install")
        def remote_install(key: str, request: Request, payload: dict | None = None):
            self.actor(request, "run")
            body = payload or {}
            status = service.remotes.setup_status(key)
            if status.get("running"):
                return {"started": False, "running": True}
            secret = {name: str(body[name]) for name in ("password", "passphrase") if body.get(name)}
            force = bool(body.get("force"))

            def work():
                try:
                    service.remotes.connect(key, secret, install=True, force=force)
                except Exception:
                    pass

            threading.Thread(target=work, name="operon-remote-install", daemon=True).start()
            return {"started": True, "running": True}

        @app.get("/api/agent/remote/{key}/setup")
        def remote_setup(key: str, request: Request):
            self.actor(request, "context")
            return service.remotes.setup_status(key)

        @app.get("/api/agent/remote/{key}/pool")
        def remote_pool(key: str, request: Request):
            self.actor(request, "context")
            return service.remotes.pool_info(key)

        @app.post("/api/agent/remote/{key}/pool/stop")
        def remote_pool_stop(key: str, request: Request, payload: dict | None = None):
            self.actor(request, "run")
            return service.remotes.pool_stop(key, force=bool((payload or {}).get("force")))

        @app.get("/api/agent/remote/{key}/environments")
        def remote_environments(key: str, request: Request):
            self.actor(request, "context")
            return service.remotes.environments(key)

        @app.post("/api/agent/remote/{key}/environments/prepare")
        def remote_environments_prepare(key: str, request: Request, payload: dict | None = None):
            self.actor(request, "plugins")
            body = payload or {}
            return service.remotes.prepare_environments(
                key, names=body.get("names"), dependencies=bool(body.get("dependencies")))

        @app.get("/api/agent/remote/{key}/environments/{name}/log")
        def remote_environment_log(key: str, name: str, request: Request, limit: int = 200):
            self.actor(request, "context")
            return service.remotes.environment_log(key, name, limit=limit)

        @app.get("/api/agent/sessions")
        def sessions(request: Request):
            self.actor(request, "context")
            return hub.list()

        @app.post("/api/agent/sessions")
        def create_session(request: Request, payload: dict):
            self.actor(request, "edit")
            return hub.create(payload["workspace"], payload.get("name", "Operon"))

        @app.get("/api/agent/sessions/{session}")
        def snapshot(session: str, request: Request):
            self.actor(request, "context")
            return hub.get(session)

        @app.post("/api/agent/sessions/{session}/sync")
        def sync(session: str, request: Request, payload: dict):
            if self.actor(request, "edit") != "user":
                raise HTTPException(403, "Agents must use graph commands instead of replacing the UI workspace")
            return hub.sync(session, payload["workspace"], payload["expected_revision"])

        @app.post("/api/agent/sessions/{session}/presence")
        def presence(session: str, request: Request, payload: dict):
            if self.actor(request, "edit") != "user":
                raise HTTPException(403, "Only the UI publishes user selection")
            return hub.presence(session, payload)

        @app.get("/api/agent/sessions/{session}/context")
        def context(session: str, request: Request, scope: str = "selection"):
            return hub.context(session, scope, self.actor(request, "context"))

        @app.post("/api/agent/sessions/{session}/apply")
        def apply(session: str, request: Request, payload: dict):
            actor = self.actor(request, "edit")
            try:
                return hub.apply(session, payload["document_id"], payload["expected_revision"], payload["commands"],
                                 actor, payload.get("request_id"))
            except (KeyError, ValidationError) as error:
                raise CommandError("invalid_commands", str(error)) from error

        @app.post("/api/agent/sessions/{session}/open")
        def open_graph(session: str, request: Request, payload: dict):
            return hub.open(session, payload["graph"], payload["expected_revision"], self.actor(request, "edit"),
                            document_id=payload.get("document_id"), mode=payload.get("mode", "append"))

        @app.post("/api/agent/sessions/{session}/undo")
        def undo(session: str, request: Request, payload: dict):
            return hub.undo(session, payload["document_id"], payload["expected_revision"], payload.get("redo", False), self.actor(request, "edit"),
                            transaction_id=payload.get('transaction_id'))

        @app.get("/api/agent/sessions/{session}/events")
        def events(session: str, request: Request, after: int = 0, limit: int = 50):
            self.actor(request, "context")
            return hub.events(session, after, limit)

        @app.get('/api/agent/sessions/{session}/transactions/{transaction_id}')
        def diff(session: str, transaction_id: str, request: Request, offset: int = 0, limit: int = 20):
            self.actor(request, 'context')
            return hub.diff(session, transaction_id, offset, limit)

        @app.get("/api/agent/sessions/{session}/stream")
        async def stream(session: str, request: Request, after: int = 0):
            self.actor(request, "context")
            async def emit():
                cursor = after
                while not await request.is_disconnected():
                    # Revocation also terminates an established event stream.
                    try:
                        self.actor(request, "context")
                    except HTTPException:
                        break
                    result = hub.events(session, cursor)
                    if result["events"] or result["reset"]:
                        yield "data: " + json.dumps(result, ensure_ascii=False) + "\n\n"
                        cursor = result['next_cursor']
                    else:
                        yield ": heartbeat\n\n"
                    await asyncio.sleep(.35)
            return StreamingResponse(emit(), media_type="text/event-stream")

        @app.get("/api/agent/catalog")
        def catalog(request: Request):
            self.actor(request, "context")
            return service.catalog

        @app.post("/api/agent/validate")
        def validate(request: Request, payload: dict):
            self.actor(request, "context")
            application = getattr(service, 'application', None)
            if application is not None:
                return application.validate(payload['graph'], require_files=payload.get('require_files', False))
            from operon.documents import layout
            graph = Graph.model_validate(layout(payload["graph"]))
            executions = getattr(service, 'executions', None)
            result = (executions.validate(graph, require_files=payload.get('require_files', False))
                      if executions and executions.applies(graph) else
                      service.validate_graph(graph, require_files=payload.get("require_files", False)))
            return {**result, "graph": graph.model_dump(mode="json")}

        @app.post("/api/agent/sessions/{session}/run")
        def run(session: str, request: Request, payload: dict):
            self.actor(request, "run")
            snapshot = hub.get(session)
            if payload["expected_revision"] != snapshot["revision"]:
                raise CommandError("revision_conflict", "Canvas changed before run", 409)
            doc = next((d for d in snapshot["workspace"]["documents"] if d["id"] == payload["document_id"]), None)
            if doc is None:
                raise CommandError("not_found", "Unknown document", 404)
            application = getattr(service, 'application', None)
            if application is not None:
                return application.jobs.submit({'graph': doc['graph'], **({'request_id': payload['request_id']} if payload.get('request_id') else {})})
            graph = Graph.model_validate(doc['graph'])
            executions = getattr(service, 'executions', None)
            return executions.launch(graph) if executions and executions.applies(graph) else service.launch(graph)

        @app.get("/api/agent/jobs/{job}")
        def job(job: str, request: Request):
            self.actor(request, "context")
            application = getattr(service, 'application', None)
            if application is not None:
                return application.jobs.details(job)
            executions = getattr(service, 'executions', None)
            return executions.details(job) if executions and executions.owns(job) else service.details(job)

        @app.post("/api/agent/jobs/{job}/cancel")
        def cancel(job: str, request: Request):
            self.actor(request, "run")
            application = getattr(service, 'application', None)
            if application is not None:
                return application.jobs.cancel(job)
            executions = getattr(service, 'executions', None)
            return executions.cancel(job) if executions and executions.owns(job) else service.cancel(job)

        @app.get("/api/agent/plugins")
        def plugins(request: Request):
            self.actor(request, "context")
            return service.plugins.state()

        @app.post("/api/agent/plugins/install")
        def install(request: Request, payload: dict):
            self.actor(request, "plugins")
            try:
                result = service.plugins.install(payload["wheel"])
                service.refresh_catalog()
                return result
            except ValueError as error:
                raise CommandError("plugin_install_failed", str(error)) from error
