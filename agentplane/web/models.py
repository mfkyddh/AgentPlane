from __future__ import annotations

from pydantic import BaseModel


class HostInfo(BaseModel):
    target: str
    hostname: str
    ip: str
    label: str
    provider: str
    status: str
    last_seen: str


class HostsResponse(BaseModel):
    hosts: list[HostInfo]


class AppInfo(BaseModel):
    app: str
    target: str
    repo_name: str
    service_key: str
    control_plane: str
    public_url: str


class AppsResponse(BaseModel):
    apps: list[AppInfo]


class OperationInfo(BaseModel):
    timestamp: str
    target: str
    object_type: str
    action: str
    result: str
    op_id: str


class OperationsResponse(BaseModel):
    operations: list[OperationInfo]


class ChatMessage(BaseModel):
    type: str
    payload: dict


class ChatInbound(BaseModel):
    type: str = "chat_message"
    text: str
    token: str | None = None
