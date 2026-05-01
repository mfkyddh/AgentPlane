from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.contracts import nested_get, validate_contract

ONEPANEL_LEDGER_BEGIN = "<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->"
ONEPANEL_LEDGER_END = "<!-- END AGENTPLANE_ONEPANEL_LEDGER -->"


def _payload_path(path: Path | str) -> str:
    rendered = str(path)
    if len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":":
        return rendered
    return rendered.replace("\\", "/")


def _load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def render_rollback_entry(rollback_entry: dict[str, Any]) -> str:
    kind = rollback_entry.get("kind")
    if kind == "none":
        note = rollback_entry.get("note")
        if isinstance(note, str) and note:
            return note
        return "无独立旧控制面"
    if kind == "systemd":
        return str(rollback_entry.get("service_name", "-"))
    if kind == "1panel-app":
        app_key = rollback_entry.get("app_key", "-")
        install_id = rollback_entry.get("install_id")
        container_name = rollback_entry.get("container_name")
        parts = [str(app_key)]
        if install_id is not None:
            parts.append(f"install_id={install_id}")
        if isinstance(container_name, str) and container_name:
            parts.append(f"container={container_name}")
        return f"1panel-app ({', '.join(parts)})"
    if kind == "1panel-compose":
        project_name = rollback_entry.get("project_name", "-")
        container_name = rollback_entry.get("container_name")
        project_path = rollback_entry.get("project_path")
        compose_file = rollback_entry.get("compose_file")
        parts = [str(project_name)]
        if isinstance(container_name, str) and container_name:
            parts.append(f"container={container_name}")
        if isinstance(project_path, str) and project_path:
            parts.append(f"path={project_path}")
        if isinstance(compose_file, str) and compose_file:
            parts.append(f"compose={compose_file}")
        return f"1panel-compose ({', '.join(parts)})"
    return json.dumps(rollback_entry, ensure_ascii=False, sort_keys=True)


def _output_app_resource_summary(app_resource_summary: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(app_resource_summary, dict):
        return {}

    summary: dict[str, dict[str, Any]] = {}
    for kind in ("postgres", "redis", "minio"):
        item = app_resource_summary.get(kind)
        if not isinstance(item, dict):
            continue
        normalized = {key: value for key, value in item.items() if value not in (None, "")}
        if kind == "redis":
            normalized.pop("user", None)
        if normalized:
            summary[kind] = normalized
    return summary


def _render_server_readme(target: str, inventory: dict[str, Any]) -> str:
    lines = [f"# {target} 摘要", "", "## 身份", ""]
    if "label" in inventory:
        lines.append(f"- 备注：`{inventory['label']}`")
    if "provider" in inventory:
        lines.append(f"- 云厂商：`{inventory['provider']}`")
    if "public_ip" in inventory:
        lines.append(f"- 公网 IPv4：`{inventory['public_ip']}`")
    if "public_domain" in inventory:
        lines.append(f"- 域名：`{inventory['public_domain']}`")
    aliases = inventory.get("ssh", {}).get("aliases", [])
    if aliases:
        lines.append(f"- SSH 别名：`{aliases[0]}`")

    lines.extend(["", "## 应用控制面", ""])
    services = inventory.get("services", {})
    has_app_resource_summary = False
    if isinstance(services, dict):
        for service_name, service in sorted(services.items()):
            if not isinstance(service, dict) or "control_plane" not in service:
                continue
            lines.append(
                f"- `{service_name}`：`{service.get('control_plane', 'unknown')}` / "
                f"`{service.get('container_name', '-')}` / `{service.get('public_url', '-')}`"
            )
            depends = service.get("depends_on_containers")
            if isinstance(depends, list) and depends:
                lines.append(f"- 依赖容器：`{', '.join(depends)}`")
            app_resource_summary = _output_app_resource_summary(service.get("app_resource_summary"))
            if app_resource_summary:
                has_app_resource_summary = True
                for kind in ("postgres", "redis", "minio"):
                    item = app_resource_summary.get(kind)
                    if isinstance(item, dict) and item:
                        lines.append(
                            f"- app_resource_summary.{kind}：`{json.dumps(item, ensure_ascii=False, sort_keys=True)}`"
                        )

    if target == "prod0-main" and has_app_resource_summary:
        lines.extend(
            [
                "",
                "## App Resource 台账语义",
                "",
                "- `app_resource_summary` 供 prod0 台账与对账使用；只有 Redis 采用共享 runtime 凭据，PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。",
                "- Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户，不再把 per-app Redis user 视为活跃运行时依赖。",
                "- MinIO 当前按 bucket-scoped policy 收敛：`policy_name` / `policy_scope` / `isolation_level` 反映控制面登记的对象存储权限边界。",
                "- 这不是强隔离；它仅提供逻辑分区，真实 secret 仍需由受控 secrets 流程单独写入。",
            ]
        )

    lines.extend(
        [
            "",
            "## 资料入口",
            "",
            f"- 结构化清单：`inventory/servers/{target}/inventory.json`",
            f"- 机器真源：`inventory/servers/{target}/inventory.json`",
            f"- 本摘要：`inventory/servers/{target}/README.md`",
            "- README 只保留非敏感摘要，不承载第二真源；脚本消费和对象细节以 JSON 为准。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_app_summary(contract: dict[str, Any], target: str, inventory_entry: dict[str, Any]) -> str:
    contract_file = str(nested_get(contract, "_meta.contract_file") or "deploy/agentplane/contract.yaml")
    app_root = Path(str(nested_get(contract, "_meta.app_root") or "."))
    try:
        contract_label = Path(contract_file).resolve().relative_to(app_root.resolve()).as_posix()
    except ValueError:
        contract_label = _payload_path(contract_file)
    public_url = str(inventory_entry.get("public_url", "-"))
    access_label = "公网入口"
    if public_url.startswith("internal://"):
        access_label = "内网探针"
    lines = [
        f"# {contract['app_id']} AgentPlane 交接摘要",
        "",
        "本文件是应用仓库面向业务开发者的非敏感部署摘要。生产控制面真源在 `AgentPlane` 仓库，而不是当前应用仓库。",
        "",
        f"- 目标环境：`{target}`",
        f"- 控制面：`{inventory_entry.get('control_plane', '-')}`",
        f"- 容器名：`{inventory_entry.get('container_name', '-')}`",
        f"- {access_label}：`{public_url}`",
        f"- 回滚入口：`{render_rollback_entry(inventory_entry.get('rollback_entry', {}))}`",
    ]
    depends = inventory_entry.get("depends_on_containers")
    if isinstance(depends, list) and depends:
        lines.append(f"- 依赖容器：`{', '.join(depends)}`")
    app_resource_summary = _output_app_resource_summary(inventory_entry.get("app_resource_summary"))
    lines.extend(["", "## App Resource 资源摘要（非敏感）", ""])
    if app_resource_summary:
        for kind in ("postgres", "redis", "minio"):
            item = app_resource_summary.get(kind)
            if isinstance(item, dict) and item:
                lines.append(f"- `{kind}`：`{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
    else:
        lines.append("- 未登记 app_resource_summary。")
    if target == "prod0-main" and app_resource_summary:
        lines.extend(
            [
                "",
                "## App Resource 语义说明",
                "",
                "- 当前文档中的 `app_resource_summary` 只保留租户识别所需的非敏感信息；PostgreSQL/MinIO 仍按各自租户凭据接入，其中 MinIO 额外记录 bucket-scoped policy 元数据。",
                "- Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户；这不是强隔离，也不要求 per-app Redis user 作为活跃运行时依赖。",
                "- MinIO 的 `policy_name` / `policy_scope` / `isolation_level` 仅表达登记后的权限边界，不暴露真实 secret。",
            ]
        )
    lines.extend(
        [
            "",
            "## 交付合同",
            "",
            f"- 合同文件：`{contract_label}`",
            "- 正式部署、网站对象、回滚与台账刷新统一在 `AgentPlane` 仓库执行。",
        ]
    )
    return "\n".join(lines) + "\n"


def _preserve_onepanel_ledger_section(existing: str, rendered: str) -> str:
    if ONEPANEL_LEDGER_BEGIN not in existing or ONEPANEL_LEDGER_END not in existing:
        return rendered
    if ONEPANEL_LEDGER_BEGIN in rendered and ONEPANEL_LEDGER_END in rendered:
        return rendered
    _before, _, rest = existing.partition(ONEPANEL_LEDGER_BEGIN)
    section_body, _, _after = rest.partition(ONEPANEL_LEDGER_END)
    section = f"{ONEPANEL_LEDGER_BEGIN}{section_body}{ONEPANEL_LEDGER_END}\n"
    return rendered.rstrip() + "\n\n" + section


def _resolve_app_summary_path(contract: dict[str, Any], *, target: str) -> str | None:
    summary_paths = nested_get(contract, "docs.app_summary_files")
    if isinstance(summary_paths, dict):
        target_path = summary_paths.get(target)
        if isinstance(target_path, str) and target_path:
            return target_path
    summary_path = nested_get(contract, "docs.app_summary_file")
    if isinstance(summary_path, str) and summary_path:
        return summary_path
    return None


def doc_sync(*, repo_root: Path, target: str, contract_paths: list[Path], write: bool) -> dict[str, Any]:
    inventory_file, inventory = _load_inventory(repo_root, target)
    server_readme = inventory_file.with_name("README.md")
    app_docs: list[str] = []

    if write:
        current_readme = server_readme.read_text(encoding="utf-8") if server_readme.is_file() else ""
        rendered_readme = _preserve_onepanel_ledger_section(current_readme, _render_server_readme(target, inventory))
        server_readme.write_text(rendered_readme, encoding="utf-8")

    for contract_path in contract_paths:
        contract = validate_contract(contract_path, repo_root=repo_root, target=target)
        service_key = nested_get(contract, "inventory.service_key") or contract["app_id"]
        entry = inventory.get("services", {}).get(service_key, {})
        if not isinstance(entry, dict):
            entry = {}
        summary_path = _resolve_app_summary_path(contract, target=target)
        if isinstance(summary_path, str) and summary_path:
            app_root = Path(contract["_meta"]["app_root"])
            output_file = app_root / summary_path
            app_docs.append(_payload_path(output_file))
            if write:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(_render_app_summary(contract, target, entry), encoding="utf-8")

    return {"server_readme": _payload_path(server_readme), "app_docs": app_docs}
