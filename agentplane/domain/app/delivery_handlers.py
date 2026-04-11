from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from agentplane.domain.app.catalog import resolve_app_contract_source
from agentplane.domain.app.lifecycle import (
    offboard_delivery_for_app,
    onboard_delivery_for_app,
    run_delivery_post_actions,
)


_OBSERVATION_WINDOW_NOTE = "旧 runtime 作为 rollback state 保留；只有 post-cutover verification 通过且 observation window 结束后才允许清理。"
def _resolve_contract_file(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None,
) -> Path:
    _, contract_file = resolve_app_contract_source(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    return contract_file


def _load_validated_contract(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> tuple[Any, dict[str, Any], Path]:
    from agentplane.cli import apps as app_cli

    contract_file = _resolve_contract_file(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    contract = app_cli.validate_contract(contract_file, repo_root=repo_root, target=target)
    return app_cli, contract, contract_file


def _candidate_host_binding(app_cli: Any, host_binding: str) -> str:
    host_ip, host_port = app_cli._split_host_binding(host_binding)
    port = int(host_port)
    if port <= 64535:
        candidate_port = port + 1000
    elif port > 1000:
        candidate_port = port - 1000
    else:
        raise ValueError(f"无法为 candidate runtime 推导预检端口: {host_binding}")
    return f"{host_ip}:{candidate_port}"


def _candidate_runtime_material(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_ref: str | None,
    rollout_id: str,
    persist_local_compose: bool,
) -> dict[str, Any]:
    app_id = str(contract["app_id"])
    suffix = rollout_id.replace("-", "")[-8:]
    runtime = deepcopy(contract["runtime"])
    base_container_name = app_cli._runtime_container_name(app_id, runtime, target=target)
    candidate_runtime = dict(runtime)
    candidate_runtime["container_name"] = f"{base_container_name}-candidate-{suffix}"
    candidate_runtime["host_binding"] = _candidate_host_binding(app_cli, str(runtime["host_binding"]))

    candidate_contract = deepcopy(contract)
    candidate_contract["runtime"] = candidate_runtime
    rendered = app_cli.render_runtime(candidate_contract, repo_root=repo_root, target=target, image_ref=image_ref)

    compose_payload = yaml.safe_load(str(rendered["compose"]))
    if not isinstance(compose_payload, dict):
        raise ValueError("candidate rendered compose 必须是对象")
    services = compose_payload.get("services")
    if not isinstance(services, dict):
        raise ValueError("candidate rendered compose 缺少 services")
    service = services.get(app_id)
    if not isinstance(service, dict):
        raise ValueError(f"candidate rendered compose 缺少 services.{app_id}")

    remote_compose_name = app_cli._remote_compose_filename(target).removesuffix(".yml") + f".candidate.{suffix}.yml"
    remote_compose_dir = f"/opt/agentplane/infra/compose/{app_id}"
    remote_compose = f"{remote_compose_dir}/{remote_compose_name}"
    remote_env = f"/opt/agentplane/secrets/services/{app_id}.{app_cli._target_alias(target)}.candidate.{suffix}.env"
    service["env_file"] = [remote_env]
    candidate_compose_text = yaml.safe_dump(compose_payload, sort_keys=False, allow_unicode=False)

    local_compose = repo_root / "tmp" / "rendered-compose" / f"{app_id}-{suffix}-candidate.yml"
    if persist_local_compose:
        local_compose.parent.mkdir(parents=True, exist_ok=True)
        local_compose.write_text(candidate_compose_text, encoding="utf-8")

    health_path = str(candidate_runtime["healthcheck"]["path"])
    _, candidate_port = app_cli._split_host_binding(str(candidate_runtime["host_binding"]))
    return {
        "rollout_id": rollout_id,
        "contract": candidate_contract,
        "compose_text": candidate_compose_text,
        "container_name": str(candidate_runtime["container_name"]),
        "project_name": f"{app_id}-candidate-{suffix}",
        "host_binding": str(candidate_runtime["host_binding"]),
        "health_url": f"http://127.0.0.1:{candidate_port}{health_path}",
        "local_compose": local_compose,
        "local_env": app_cli._service_env_path(repo_root, app_id, target),
        "remote_compose_dir": remote_compose_dir,
        "remote_compose_name": remote_compose_name,
        "remote_compose": remote_compose,
        "remote_env": remote_env,
    }


def _candidate_precheck_steps(app_cli: Any, repo_root: Path, *, target: str, material: dict[str, Any]) -> dict[str, list[tuple[list[str], str]]]:
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    local_env = Path(material["local_env"])
    remote_tmp_env = f"/tmp/{local_env.name}"
    up_command = (
        f"cd {material['remote_compose_dir']} && "
        f"docker compose -p {material['project_name']} -f {material['remote_compose_name']} up -d --pull never"
    )
    down_command = (
        f"cd {material['remote_compose_dir']} && "
        f"docker compose -p {material['project_name']} -f {material['remote_compose_name']} down || true"
    )
    cleanup_remote_command = f"rm -f {material['remote_compose']} {material['remote_env']}"
    origin_health_wait = app_cli._origin_health_wait_command(material["contract"], container_name=str(material["container_name"]))
    prepare = [
        (
            ssh_target.ssh_args_for_shell(f"mkdir -p {material['remote_compose_dir']} /opt/agentplane/secrets/services"),
            ssh_target.display_ssh_command(f"mkdir -p {material['remote_compose_dir']} /opt/agentplane/secrets/services"),
        ),
        (
            ["scp", "-F", str(ssh_target.config_path), str(material["local_compose"]), ssh_target.scp_destination(str(material["remote_compose"]))],
            ssh_target.display_scp_command(str(material["local_compose"]), str(material["remote_compose"])),
        ),
        (
            ["scp", "-F", str(ssh_target.config_path), str(local_env), ssh_target.scp_destination(remote_tmp_env)],
            ssh_target.display_scp_command(str(local_env), remote_tmp_env),
        ),
        (
            ssh_target.ssh_args_for_shell(f"install -Dm600 {remote_tmp_env} {material['remote_env']} && rm -f {remote_tmp_env}"),
            ssh_target.display_ssh_command(f"install -Dm600 {remote_tmp_env} {material['remote_env']} && rm -f {remote_tmp_env}"),
        ),
        (
            ssh_target.ssh_args_for_shell(up_command),
            ssh_target.display_ssh_command(up_command),
        ),
    ]
    verify = [
        (
            ssh_target.ssh_args_for_shell(f"docker inspect {material['container_name']}"),
            ssh_target.display_ssh_command(f"docker inspect {material['container_name']}"),
        ),
        (
            ssh_target.ssh_args_for_shell(origin_health_wait),
            ssh_target.display_ssh_command(origin_health_wait),
        ),
    ]
    cleanup = [
        (
            ssh_target.ssh_args_for_shell(down_command),
            ssh_target.display_ssh_command(down_command),
        ),
        (
            ssh_target.ssh_args_for_shell(cleanup_remote_command),
            ssh_target.display_ssh_command(cleanup_remote_command),
        ),
    ]
    return {"prepare": prepare, "verify": verify, "cleanup": cleanup}


def _run_steps(app_cli: Any, steps: list[tuple[list[str], str]], *, stop_on_failure: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for argv, display in steps:
        result = app_cli._execute_step(argv=argv, display=display)
        results.append(result)
        if stop_on_failure and not result["ok"]:
            break
    return results


def _plan_production_verify(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    include_public: bool,
) -> dict[str, Any]:
    container_name = app_cli._runtime_container_name(str(contract["app_id"]), contract["runtime"], target=target)
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    origin_health_wait = app_cli._origin_health_wait_command(contract, container_name=container_name)
    commands = [
        ssh_target.display_ssh_command(f"docker inspect {container_name}"),
        ssh_target.display_ssh_command(origin_health_wait),
    ]
    if include_public and app_cli._has_public_ingress(contract):
        public_root = str(app_cli._public_sites(contract)[0]["public_url"]).rstrip("/")
        commands.extend(
            [
                f"curl -fsS {public_root}{contract['runtime']['healthcheck']['path']}",
                f"curl -fsSI {public_root}/",
            ]
        )
    return {"container_name": container_name, "commands": commands, "status": "planned"}


def _execute_origin_verify(app_cli: Any, contract: dict[str, Any], *, repo_root: Path, target: str) -> dict[str, Any]:
    container_name = app_cli._runtime_container_name(str(contract["app_id"]), contract["runtime"], target=target)
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    origin_health_wait = app_cli._origin_health_wait_command(contract, container_name=container_name)
    checks = [
        app_cli._execute_step(
            argv=ssh_target.ssh_args_for_shell(f"docker inspect {container_name}"),
            display=ssh_target.display_ssh_command(f"docker inspect {container_name}"),
        ),
        app_cli._execute_step(
            argv=ssh_target.ssh_args_for_shell(origin_health_wait),
            display=ssh_target.display_ssh_command(origin_health_wait),
        ),
    ]
    return {
        "container_name": container_name,
        "network_preflight": app_cli._production_network_preflight(repo_root, target),
        "commands": [item["display"] for item in checks],
        "checks": {"origin": checks, "public": []},
        "ok": all(item["ok"] for item in checks),
    }


def _plan_production_rollback(app_cli: Any, contract: dict[str, Any], *, repo_root: Path, target: str) -> dict[str, Any]:
    rollback_entry = contract["rollback"]["previous_control_plane"]
    if rollback_entry.get("kind") == "none":
        return {
            "rollback_entry": rollback_entry,
            "commands": [],
            "warning": app_cli._render_rollback_entry(rollback_entry),
            "status": "not-applicable",
        }
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    transition_step = app_cli._control_plane_transition_step(repo_root, target=target, rollback_entry=rollback_entry, operate="start")
    commands = [
        ssh_target.display_ssh_command(
            f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {app_cli._remote_compose_filename(target)} down || true"
        )
    ]
    if transition_step:
        commands.append(transition_step[1])
    return {"rollback_entry": rollback_entry, "commands": commands, "status": "planned"}


def _delayed_cleanup_state(rollback_entry: dict[str, Any]) -> dict[str, Any]:
    kind = rollback_entry.get("kind")
    if kind == "none":
        return {
            "status": "not-applicable",
            "rollback_entry": rollback_entry,
            "observation_window_required": False,
            "commands": [],
            "note": "无旧 runtime 可保留或清理。",
        }
    return {
        "status": "observation-window-pending",
        "rollback_entry": rollback_entry,
        "observation_window_required": True,
        "commands": [],
        "note": _OBSERVATION_WINDOW_NOTE,
    }


def _rollback_state_payload(
    *,
    previous_control_plane: dict[str, Any],
    candidate: dict[str, Any],
    cutover: dict[str, Any],
    post_cutover_verification: dict[str, Any],
    rollback_on_failure: dict[str, Any],
    delayed_cleanup: dict[str, Any],
) -> dict[str, Any]:
    return {
        "previous_control_plane": previous_control_plane,
        "candidate": candidate,
        "cutover": cutover,
        "post_cutover_verification": post_cutover_verification,
        "rollback_on_failure": rollback_on_failure,
        "delayed_cleanup": delayed_cleanup,
    }


def _run_delivery_post_actions(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    write: bool,
    write_evidence: bool,
    deploy_operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_delivery_post_actions(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        write=write,
        write_evidence=write_evidence,
        evidence_action="deploy",
        evidence_op_prefix="deploy-post-actions",
        deploy_operation=deploy_operation,
    )


def onboard_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> dict[str, Any]:
    payload = onboard_delivery_for_app(
        repo_root,
        target=target,
        app=app,
        dry_run=dry_run,
        write=write,
        app_repo_root=app_repo_root,
        repo_name=repo_name,
        contract_path=contract_path,
    )
    return {"command": "app", "action": "onboard", "target": target, "payload": payload}


def offboard_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
) -> dict[str, Any]:
    payload = offboard_delivery_for_app(repo_root, target=target, app=app, dry_run=dry_run, write=write)
    return {"command": "app", "action": "offboard", "target": target, "payload": payload}


def validate_contract_for_app(repo_root: Path, *, target: str, app: str, app_repo_root: str | None = None) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    return {"command": "app", "action": "validate-contract", "valid": True, "payload": contract}


def render_runtime_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)
    return {"command": "app", "action": "render-runtime", "payload": payload}


def inventory_refresh_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    write: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, _, contract_file = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.inventory_refresh(repo_root=repo_root, target=target, contract_paths=[contract_file], write=write)
    return {"command": "app", "action": "inventory-refresh", "target": target, "payload": payload}


def doc_sync_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    write: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, _, contract_file = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.doc_sync(repo_root=repo_root, target=target, contract_paths=[contract_file], write=write)
    return {"command": "app", "action": "doc-sync", "target": target, **payload}


def build_artifact_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.build_artifact(
        contract,
        repo_root=repo_root,
        target=target,
        image_tag=image_tag,
        auto_version=auto_version,
        dry_run=dry_run,
    )
    return {"command": "app", "action": "build-artifact", "payload": payload}


def package_runtime_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.package_runtime(
        contract,
        repo_root=repo_root,
        target=target,
        image_tag=image_tag,
        auto_version=auto_version,
        dry_run=dry_run,
    )
    return {"command": "app", "action": "package-runtime", "payload": payload}


def ship_image_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    archive_dir: Path,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.ship_image(contract, repo_root=repo_root, target=target, image_ref=image_ref, archive_dir=archive_dir, dry_run=dry_run)
    return {"command": "app", "action": "ship-image", "target": target, "payload": payload}


def deploy_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    rollback_entry = contract["rollback"]["previous_control_plane"]

    if target == "wsl":
        payload = app_cli.deploy_app(contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=dry_run, execute=execute)
        if payload.get("ok", False) and (dry_run or execute):
            payload["post_actions"] = _run_delivery_post_actions(
                repo_root,
                target=target,
                app=app,
                app_repo_root=app_repo_root,
                write=execute and not dry_run,
                write_evidence=execute and not dry_run,
                deploy_operation=payload.get("operation"),
            )
            if execute and not payload["post_actions"].get("ok", False):
                payload["ok"] = False
        payload["rollback_state"] = {
            "status": "not-applicable",
            "previous_control_plane": rollback_entry,
            "note": "wsl 本地开发路径不执行 production cutover rollback-state 编排。",
        }
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    rollout_id = app_cli.next_operation_id("deploy-cutover")
    candidate_material = _candidate_runtime_material(
        app_cli,
        contract,
        repo_root=repo_root,
        target=target,
        image_ref=image_ref,
        rollout_id=rollout_id,
        persist_local_compose=execute,
    )
    candidate_steps = _candidate_precheck_steps(app_cli, repo_root, target=target, material=candidate_material)

    candidate_plan = {
        "status": "planned",
        "container_name": candidate_material["container_name"],
        "project_name": candidate_material["project_name"],
        "host_binding": candidate_material["host_binding"],
        "health_url": candidate_material["health_url"],
        "local_compose": str(candidate_material["local_compose"]),
        "local_env": str(candidate_material["local_env"]),
        "remote_compose": candidate_material["remote_compose"],
        "remote_env": candidate_material["remote_env"],
        "commands": [display for phase in ("prepare", "verify", "cleanup") for _, display in candidate_steps[phase]],
    }
    rollback_plan = _plan_production_rollback(app_cli, contract, repo_root=repo_root, target=target)
    delayed_cleanup = _delayed_cleanup_state(rollback_entry)

    if dry_run:
        cutover_plan = app_cli.deploy_app(contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=True, execute=False)
        verify_plan = _plan_production_verify(app_cli, contract, repo_root=repo_root, target=target, include_public=False)
        cutover_plan["rollback_state"] = _rollback_state_payload(
            previous_control_plane=rollback_entry,
            candidate=candidate_plan,
            cutover={"status": "planned", "commands": cutover_plan["commands"]},
            post_cutover_verification=verify_plan,
            rollback_on_failure=rollback_plan,
            delayed_cleanup=delayed_cleanup,
        )
        cutover_plan["commands"] = [
            *candidate_plan["commands"],
            *cutover_plan["commands"],
            *verify_plan["commands"],
            *rollback_plan["commands"],
        ]
        cutover_plan["post_actions"] = _run_delivery_post_actions(
            repo_root,
            target=target,
            app=app,
            app_repo_root=app_repo_root,
            write=False,
            write_evidence=False,
            deploy_operation=cutover_plan.get("operation"),
        )
        cutover_plan["deployment_model"] = "formal-rollback-state"
        return {"command": "app", "action": "deploy", "target": target, "payload": cutover_plan}

    if not execute:
        payload = app_cli.deploy_app(contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=False, execute=False)
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    app_cli._production_network_preflight(repo_root, target)
    local_env = Path(candidate_material["local_env"])
    if not local_env.is_file():
        raise ValueError(f"缺少运行时 env 文件: {local_env}")

    prepare_results = _run_steps(app_cli, candidate_steps["prepare"], stop_on_failure=True)
    prepare_ok = len(prepare_results) == len(candidate_steps["prepare"]) and all(item["ok"] for item in prepare_results)
    verify_results = _run_steps(app_cli, candidate_steps["verify"], stop_on_failure=True) if prepare_ok else []
    verify_ok = len(verify_results) == len(candidate_steps["verify"]) and all(item["ok"] for item in verify_results)
    cleanup_results = _run_steps(app_cli, candidate_steps["cleanup"], stop_on_failure=False)
    cleanup_ok = len(cleanup_results) == len(candidate_steps["cleanup"]) and all(item["ok"] for item in cleanup_results)

    executed_candidate = {
        **candidate_plan,
        "status": "verified" if prepare_ok and verify_ok and cleanup_ok else "failed",
        "results": {
            "prepare": prepare_results,
            "verify": verify_results,
            "cleanup": cleanup_results,
        },
    }

    if not (prepare_ok and verify_ok and cleanup_ok):
        operation = app_cli._record_app_operation(
            repo_root,
            action="deploy",
            target=target,
            dry_run=False,
            operation={"op_id": rollout_id, "target": target, "result": "candidate-precheck-failed"},
            details={
                "artifact_summary": f"{contract['app_id']} candidate precheck",
                "rollback_entry": rollback_entry,
            },
        )
        payload = {
            "ok": False,
            "operation": operation,
            "deployment_model": "formal-rollback-state",
            "commands": executed_candidate["commands"],
            "rollback_state": _rollback_state_payload(
                previous_control_plane=rollback_entry,
                candidate=executed_candidate,
                cutover={"status": "skipped", "reason": "candidate pre-cutover verification failed", "commands": []},
                post_cutover_verification={"status": "skipped", "commands": []},
                rollback_on_failure={"status": "not-needed", **rollback_plan},
                delayed_cleanup=delayed_cleanup,
            ),
        }
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    cutover_payload = app_cli.deploy_app(contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=False, execute=True)
    cutover_commands = list(cutover_payload.get("commands", []))
    aggregate_commands = [*executed_candidate["commands"], *cutover_commands]

    if not cutover_payload.get("ok", False):
        rollback_payload = app_cli.rollback_app(contract, repo_root=repo_root, target=target, dry_run=False, execute=True)
        payload = {
            **cutover_payload,
            "ok": False,
            "commands": [*aggregate_commands, *rollback_payload.get("commands", [])],
            "deployment_model": "formal-rollback-state",
            "rollback_state": _rollback_state_payload(
                previous_control_plane=rollback_entry,
                candidate=executed_candidate,
                cutover={"status": "failed", "commands": cutover_commands, "result": cutover_payload.get("results", [])},
                post_cutover_verification={"status": "skipped", "commands": []},
                rollback_on_failure={
                    "status": "executed" if rollback_payload.get("ok", False) else "failed",
                    **rollback_payload,
                },
                delayed_cleanup=delayed_cleanup,
            ),
        }
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    verify_payload = _execute_origin_verify(app_cli, contract, repo_root=repo_root, target=target)
    aggregate_commands.extend(verify_payload.get("commands", []))

    if not verify_payload.get("ok", False):
        rollback_payload = app_cli.rollback_app(contract, repo_root=repo_root, target=target, dry_run=False, execute=True)
        payload = {
            **cutover_payload,
            "ok": False,
            "commands": [*aggregate_commands, *rollback_payload.get("commands", [])],
            "verification": verify_payload,
            "deployment_model": "formal-rollback-state",
            "rollback_state": _rollback_state_payload(
                previous_control_plane=rollback_entry,
                candidate=executed_candidate,
                cutover={"status": "executed", "commands": cutover_commands, "result": cutover_payload.get("results", [])},
                post_cutover_verification={
                    "status": "failed",
                    "commands": verify_payload.get("commands", []),
                    "checks": verify_payload.get("checks", {}),
                },
                rollback_on_failure={
                    "status": "executed" if rollback_payload.get("ok", False) else "failed",
                    **rollback_payload,
                },
                delayed_cleanup=delayed_cleanup,
            ),
        }
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    payload = {
        **cutover_payload,
        "ok": True,
        "commands": aggregate_commands,
        "verification": verify_payload,
        "deployment_model": "formal-rollback-state",
        "rollback_state": _rollback_state_payload(
            previous_control_plane=rollback_entry,
            candidate=executed_candidate,
            cutover={"status": "executed", "commands": cutover_commands, "result": cutover_payload.get("results", [])},
            post_cutover_verification={
                "status": "verified",
                "commands": verify_payload.get("commands", []),
                "checks": verify_payload.get("checks", {}),
            },
            rollback_on_failure={"status": "standby", **rollback_plan},
            delayed_cleanup=delayed_cleanup,
        ),
    }
    post_actions = _run_delivery_post_actions(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        write=True,
        write_evidence=True,
        deploy_operation=cutover_payload.get("operation"),
    )
    payload["post_actions"] = post_actions
    if not post_actions.get("ok", False):
        payload["ok"] = False
    return {"command": "app", "action": "deploy", "target": target, "payload": payload}


def verify_delivery_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.verify_app(contract, repo_root=repo_root, target=target, dry_run=dry_run, execute=execute)
    return {"command": "app", "action": "verify", "target": target, "payload": payload}


def rollback_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.rollback_app(contract, repo_root=repo_root, target=target, dry_run=dry_run, execute=execute)
    payload["rollback_state"] = {
        "status": "planned" if dry_run or not execute else "executed" if payload.get("ok", True) else "failed",
        "previous_control_plane": contract["rollback"]["previous_control_plane"],
    }
    return {"command": "app", "action": "rollback", "target": target, "payload": payload}
