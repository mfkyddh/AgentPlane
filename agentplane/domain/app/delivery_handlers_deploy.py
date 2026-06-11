"""Full deploy orchestration — candidate precheck, cutover, rollback-on-failure, verification."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from agentplane.domain.app.delivery_handlers_candidate import (
    _candidate_precheck_steps,
    _candidate_runtime_material,
)
from agentplane.domain.app.delivery_handlers_planning import (
    _execute_origin_verify,
    _plan_production_rollback,
    _plan_production_verify,
    _plan_remote_deploy_steps,
    _plan_wsl_deploy_steps,
)
from agentplane.domain.app.delivery_handlers_shared import (
    _check_delivery_preconditions,
    _execute_steps,
    _load_validated_contract,
    _render_execution_steps,
)
from agentplane.domain.app.delivery_handlers_state import (
    _delayed_cleanup_state,
    _rollback_state_payload,
    _run_delivery_post_actions,
)
from agentplane.runtime.backends.ssh_linux import stream_docker_image


def deploy_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
    _streamer=stream_docker_image,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)

    if execute:
        preconditions = _check_delivery_preconditions(repo_root, target=target, app=app, app_repo_root=app_repo_root)
        if not preconditions["ok"]:
            return {
                "command": "app",
                "action": "deploy",
                "target": target,
                "payload": {
                    "ok": False,
                    "error": {
                        "code": "app.delivery.precondition_failed",
                        "message": "deploy 前置检查未通过",
                        "hint": "先执行 `app object verify` 和 `app resource verify` 查看详情",
                    },
                    "preconditions": preconditions["preconditions"],
                },
            }

    rollback_entry = contract["rollback"]["previous_control_plane"]

    if target == "wsl":
        payload = app_cli.deploy_app(
            contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=dry_run, execute=execute
        )
        if dry_run:
            execution_steps, _metadata = _plan_wsl_deploy_steps(
                app_cli,
                contract,
                repo_root=repo_root,
                target=target,
                image_ref=image_ref,
            )
            rendered_steps = _render_execution_steps(execution_steps)
            payload["execution_steps"] = rendered_steps
            payload["backend_type"] = execution_steps[0].spec.backend_type
            payload["commands"] = [step["backend"]["display_command"] for step in rendered_steps]
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
    candidate_rendered = {phase: _render_execution_steps(steps) for phase, steps in candidate_steps.items()}

    candidate_plan = {
        "status": "planned",
        "container_name": candidate_material["container_name"],
        "project_name": candidate_material["project_name"],
        "host_binding": candidate_material["host_binding"],
        "health_url": candidate_material["health_url"],
        "local_compose": str(candidate_material["local_compose"]),
        "local_env": app_cli._payload_path(candidate_material["local_env"]),
        "remote_compose": candidate_material["remote_compose"],
        "remote_env": candidate_material["remote_env"],
        "commands": [
            step["backend"]["display_command"]
            for phase in ("prepare", "verify", "cleanup")
            for step in candidate_rendered[phase]
        ],
        "execution_steps": candidate_rendered,
    }
    rollback_plan = _plan_production_rollback(app_cli, contract, repo_root=repo_root, target=target)
    delayed_cleanup = _delayed_cleanup_state(rollback_entry)

    if dry_run:
        cutover_plan = app_cli.deploy_app(
            contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=True, execute=False
        )
        cutover_steps, _cutover_metadata = _plan_remote_deploy_steps(
            app_cli,
            contract,
            repo_root=repo_root,
            target=target,
            image_ref=image_ref,
        )
        cutover_execution_steps = _render_execution_steps(cutover_steps)
        verify_plan = _plan_production_verify(
            app_cli, contract, repo_root=repo_root, target=target, include_public=False
        )
        cutover_plan["execution_steps"] = cutover_execution_steps
        cutover_plan["backend_type"] = "ssh-linux"
        cutover_plan["rollback_state"] = _rollback_state_payload(
            previous_control_plane=rollback_entry,
            candidate=candidate_plan,
            cutover={
                "status": "planned",
                "commands": [step["backend"]["display_command"] for step in cutover_execution_steps],
                "execution_steps": cutover_execution_steps,
            },
            post_cutover_verification=verify_plan,
            rollback_on_failure=rollback_plan,
            delayed_cleanup=delayed_cleanup,
        )
        cutover_plan["commands"] = [
            *candidate_plan["commands"],
            *[step["backend"]["display_command"] for step in cutover_execution_steps],
            *verify_plan["commands"],
            *rollback_plan["commands"],
        ]
        effective_image_ref = image_ref or candidate_material.get("image_ref")
        if effective_image_ref:
            ssh_tgt = app_cli._target_ssh_target(repo_root, target)
            stream_cmd = f"docker save {shlex.quote(effective_image_ref)} | ssh {ssh_tgt.connection_target} docker load"
            cutover_plan["commands"].insert(0, stream_cmd)
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
        payload = app_cli.deploy_app(
            contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=False, execute=False
        )
        return {"command": "app", "action": "deploy", "target": target, "payload": payload}

    app_cli._production_network_preflight(repo_root, target)

    effective_image_ref = image_ref or candidate_material.get("image_ref")
    if effective_image_ref:
        ssh_target = app_cli._target_ssh_target(repo_root, target)
        stream_result = _streamer(effective_image_ref, ssh_target)
        if not stream_result.ok:
            raise ValueError(f"流式镜像传输失败: {stream_result.stderr}")

    local_env = Path(candidate_material["local_env"])
    if not local_env.is_file():
        raise ValueError(f"缺少运行时 env 文件: {local_env}")

    prepare_results = _execute_steps(candidate_steps["prepare"], stop_on_failure=True)
    prepare_ok = len(prepare_results) == len(candidate_steps["prepare"]) and all(item["ok"] for item in prepare_results)
    verify_results = _execute_steps(candidate_steps["verify"], stop_on_failure=True) if prepare_ok else []
    verify_ok = len(verify_results) == len(candidate_steps["verify"]) and all(item["ok"] for item in verify_results)
    cleanup_results = _execute_steps(candidate_steps["cleanup"], stop_on_failure=False)
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

    cutover_payload = app_cli.deploy_app(
        contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=False, execute=True
    )
    cutover_commands = list(cutover_payload.get("commands", []))
    aggregate_commands = [*executed_candidate["commands"], *cutover_commands]

    if not cutover_payload.get("ok", False):
        rollback_payload = app_cli.rollback_app(
            contract, repo_root=repo_root, target=target, dry_run=False, execute=True
        )
        payload = {
            **cutover_payload,
            "ok": False,
            "commands": [*aggregate_commands, *rollback_payload.get("commands", [])],
            "deployment_model": "formal-rollback-state",
            "rollback_state": _rollback_state_payload(
                previous_control_plane=rollback_entry,
                candidate=executed_candidate,
                cutover={
                    "status": "failed",
                    "commands": cutover_commands,
                    "result": cutover_payload.get("results", []),
                },
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
        rollback_payload = app_cli.rollback_app(
            contract, repo_root=repo_root, target=target, dry_run=False, execute=True
        )
        payload = {
            **cutover_payload,
            "ok": False,
            "commands": [*aggregate_commands, *rollback_payload.get("commands", [])],
            "verification": verify_payload,
            "deployment_model": "formal-rollback-state",
            "rollback_state": _rollback_state_payload(
                previous_control_plane=rollback_entry,
                candidate=executed_candidate,
                cutover={
                    "status": "executed",
                    "commands": cutover_commands,
                    "result": cutover_payload.get("results", []),
                },
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
