from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agentplane.web.agent_router import handle_chat_message
from agentplane.web.api import (
    get_app_detail,
    get_audit_log,
    get_capabilities,
    get_dashboard,
    get_data_mtime,
    get_domain_app,
    get_domain_infra,
    get_domain_ingress,
    get_domain_project,
    get_domain_service,
    get_server_detail,
    get_topology,
    list_apps,
    list_hosts,
    list_operations,
)

STATIC_DIR = Path(__file__).parent / "static"
MAX_HISTORY = 20
WS_MAX_BYTES = 64 * 1024  # 64KB


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Response-Time header to all responses."""

    async def dispatch(self, request: Request, call_next):
        import time as _time

        start = _time.monotonic()
        response = await call_next(request)
        elapsed_ms = (_time.monotonic() - start) * 1000
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            auth = request.headers.get("authorization", "")
            if not hmac.compare_digest(auth, f"Bearer {self._token}"):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


def create_app(repo_root: Path, token: str | None = None) -> FastAPI:
    app = FastAPI(title="AgentPlane", version="0.1.0")

    if token is not None:
        app.add_middleware(TokenAuthMiddleware, token=token)
    app.add_middleware(TimingMiddleware)

    @app.get("/api/dashboard")
    async def api_dashboard():
        return get_dashboard(repo_root)

    @app.get("/api/hosts")
    async def api_hosts():
        return list_hosts(repo_root)

    @app.get("/api/apps")
    async def api_apps():
        return list_apps(repo_root)

    @app.get("/api/operations")
    async def api_operations():
        return list_operations(repo_root)

    @app.get("/api/audit-log")
    async def api_audit_log(limit: int = 100, target: str | None = None):
        return get_audit_log(repo_root, limit=limit, target=target)

    @app.get("/api/mtime")
    async def api_mtime():
        return get_data_mtime(repo_root)

    @app.get("/api/topology")
    async def api_topology():
        return get_topology(repo_root)

    @app.get("/api/servers/{target}")
    async def api_server_detail(target: str):
        result = get_server_detail(repo_root, target)
        if result.get("error") == "not_found":
            return JSONResponse(result, status_code=404)
        return result

    @app.get("/api/apps/{target}/{app}")
    async def api_app_detail(target: str, app: str):
        result = get_app_detail(repo_root, target, app)
        if result.get("error") == "not_found":
            return JSONResponse(result, status_code=404)
        return result

    @app.get("/api/domains/infra")
    async def api_domain_infra():
        return get_domain_infra(repo_root)

    @app.get("/api/domains/service")
    async def api_domain_service():
        return get_domain_service(repo_root)

    @app.get("/api/domains/app")
    async def api_domain_app():
        return get_domain_app(repo_root)

    @app.get("/api/domains/ingress")
    async def api_domain_ingress():
        return get_domain_ingress(repo_root)

    @app.get("/api/domains/project")
    async def api_domain_project():
        return get_domain_project(repo_root)

    @app.get("/api/capabilities")
    async def api_capabilities(request: Request):
        data = get_capabilities()
        # ETag-based caching: hash the JSON payload
        etag = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
        if_none_match = request.headers.get("if-none-match", "")
        if if_none_match == etag:
            return JSONResponse(None, status_code=304)
        response = JSONResponse(data)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=60"
        return response

    @app.post("/api/service/plan")
    async def api_service_plan(request: Request):
        body = await request.json()
        target = body.get("target", "")
        name = body.get("name", "")
        operation = body.get("operation", "restart")
        if not target or not name:
            return JSONResponse({"error": "target and name required"}, status_code=400)
        from types import SimpleNamespace

        from agentplane.cli.service import handle_service_command
        args = SimpleNamespace(
            service_action="plan", target=target, name=name,
            operation=operation, repo_root=str(repo_root),
        )
        return handle_service_command(args)

    @app.post("/api/service/verify")
    async def api_service_verify(request: Request):
        body = await request.json()
        target = body.get("target", "")
        name = body.get("name", "")
        if not target or not name:
            return JSONResponse({"error": "target and name required"}, status_code=400)
        from types import SimpleNamespace

        from agentplane.cli.service import handle_service_command
        args = SimpleNamespace(
            service_action="verify", target=target, name=name,
            repo_root=str(repo_root),
        )
        return handle_service_command(args)

    @app.post("/api/app/delivery/deploy")
    async def api_app_delivery_deploy(request: Request):
        body = await request.json()
        target = body.get("target", "")
        app = body.get("app", "")
        execute = body.get("execute", False)
        if not target or not app:
            return JSONResponse({"error": "target and app required"}, status_code=400)
        from types import SimpleNamespace

        from agentplane.cli.apps import handle_app_command
        args = SimpleNamespace(
            app_surface="delivery",
            app_delivery_action="deploy",
            target=target,
            app=app,
            repo_root=str(repo_root),
            app_repo_root_override=None,
            image_ref=None,
            execute=execute,
            dry_run=not execute,
        )
        return handle_app_command(args)

    @app.post("/api/app/delivery/rollback")
    async def api_app_delivery_rollback(request: Request):
        body = await request.json()
        target = body.get("target", "")
        app = body.get("app", "")
        execute = body.get("execute", False)
        if not target or not app:
            return JSONResponse({"error": "target and app required"}, status_code=400)
        from types import SimpleNamespace

        from agentplane.cli.apps import handle_app_command
        args = SimpleNamespace(
            app_surface="delivery",
            app_delivery_action="rollback",
            target=target,
            app=app,
            repo_root=str(repo_root),
            app_repo_root_override=None,
            execute=execute,
            dry_run=not execute,
        )
        return handle_app_command(args)

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket):
        await websocket.accept()
        needs_auth = token is not None
        authenticated = token is None
        history: list[dict[str, str]] = []

        if needs_auth:
            await websocket.send_json({"type": "auth_required"})

        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw.encode("utf-8")) > WS_MAX_BYTES:
                    await websocket.send_json({"type": "error", "payload": {"message": "Message too large"}})
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "payload": {"message": "Invalid JSON"}})
                    continue

                if not authenticated:
                    if msg.get("type") == "auth" and hmac.compare_digest(
                        str(msg.get("token", "")), str(token)
                    ):
                        authenticated = True
                        await websocket.send_json({"type": "auth", "payload": {"status": "ok"}})
                    else:
                        await websocket.send_json({"type": "auth", "payload": {"status": "failed"}})
                        await websocket.close()
                        return
                    continue

                text = msg.get("text", "")
                if not text:
                    continue

                await websocket.send_json({"type": "chat_response", "payload": {"status": "running"}})
                result = await handle_chat_message(repo_root, text, history)
                history.append({"role": "user", "content": text})
                history.append({"role": "assistant", "content": json.dumps(result.get("payload", {}))})
                if len(history) > MAX_HISTORY:
                    history = history[-MAX_HISTORY:]
                await websocket.send_json(result)

        except WebSocketDisconnect:
            pass

    @app.websocket("/ws/status")
    async def ws_status(websocket: WebSocket):
        await websocket.accept()
        import asyncio as _aio
        try:
            while True:
                dashboard = get_dashboard(repo_root)
                await websocket.send_json({"type": "status", "payload": dashboard})
                await _aio.sleep(5)
        except WebSocketDisconnect:
            pass

    @app.websocket("/ws/logs/{target}/{container}")
    async def ws_logs(websocket: WebSocket, target: str, container: str):
        await websocket.accept()
        import asyncio as _aio
        import subprocess as _sub
        try:
            ssh_cmd = [
                "ssh", "-o", "ControlMaster=auto", "-o", "ControlPersist=60s",
                target, "docker", "logs", "-f", "--tail", "50", container
            ]

            process = _sub.Popen(
                ssh_cmd,
                stdout=_sub.PIPE,
                stderr=_sub.STDOUT,
                text=True,
                bufsize=1,
            )

            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    await websocket.send_json({
                        "type": "log",
                        "payload": {
                            "container": container,
                            "target": target,
                            "line": line.rstrip(),
                        }
                    })
                    await _aio.sleep(0.01)
            finally:
                process.terminate()
                process.wait()

        except WebSocketDisconnect:
            if 'process' in locals():
                process.terminate()
                process.wait()
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "payload": {"message": f"Failed to stream logs: {str(e)}"}
            })

    @app.get("/api/config")
    async def api_config():
        return {"requires_auth": token is not None}

    @app.get("/favicon.ico")
    async def favicon():
        from starlette.responses import Response
        return Response(status_code=204)

    @app.get("/")
    async def index():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/static/{filename:path}")
    async def static_file(filename: str):
        file_path = STATIC_DIR / filename
        if not file_path.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        response = FileResponse(str(file_path))
        if filename.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "public, max-age=30"
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    return app
