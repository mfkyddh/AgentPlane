from __future__ import annotations

import hmac
import json
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agentplane.web.agent_router import handle_chat_message
from agentplane.web.api import get_data_mtime, list_apps, list_hosts, list_operations

STATIC_DIR = Path(__file__).parent / "static"
MAX_HISTORY = 20
WS_MAX_BYTES = 64 * 1024  # 64KB


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

    @app.get("/api/hosts")
    async def api_hosts():
        return list_hosts(repo_root)

    @app.get("/api/apps")
    async def api_apps():
        return list_apps(repo_root)

    @app.get("/api/operations")
    async def api_operations():
        return list_operations(repo_root)

    @app.get("/api/mtime")
    async def api_mtime():
        return get_data_mtime(repo_root)

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

    @app.get("/api/config")
    async def api_config():
        return {"requires_auth": token is not None}

    @app.get("/")
    async def index():
        return FileResponse(str(STATIC_DIR / "index.html"))

    return app
