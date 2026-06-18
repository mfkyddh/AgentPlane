"""Build / package / ship pipeline for artifact-first app contracts.

Functions extracted from ``runtime.py`` to keep that module focused on
deployment and lifecycle orchestration.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

from agentplane.domain.app.artifacts import (
    artifact_output_path,
    require_artifact_first_contract,
)
from agentplane.domain.app.versioning import recommended_versions
from agentplane.runtime.backends.ssh_linux import stream_docker_image
from agentplane.runtime.operations import next_operation_id


def _get_runtime_helpers():
    """Lazy import to avoid circular dependency."""
    from agentplane.domain.app.runtime import (
        _record_app_operation,
        _run,
        _run_linux_backend_command,
        _target_ssh_target,
    )

    return _record_app_operation, _run, _run_linux_backend_command, _target_ssh_target


def _recommended_versions(contract: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    _, _run, _, _ = _get_runtime_helpers()

    def run_in_app_root(command: list[str], app_root: Path) -> CompletedProcess[str]:
        return _run(command, cwd=app_root)

    return recommended_versions(
        contract,
        repo_root=repo_root,
        run_in_app_root=run_in_app_root,
    )


def _maybe_recommended_versions(contract: dict[str, Any], *, repo_root: Path) -> dict[str, Any] | None:
    try:
        return _recommended_versions(contract, repo_root=repo_root)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return None


def build_artifact(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
) -> dict[str, Any]:
    _record_app_operation, _, _run_linux_backend_command, _ = _get_runtime_helpers()

    contract_spec = require_artifact_first_contract(contract)
    app_root = Path(contract["_meta"]["app_root"])
    output_path = artifact_output_path(app_root, contract_spec)
    if output_path is None:
        raise ValueError("artifact-first 合同缺少 artifact.output_path")
    recommended_versions = _maybe_recommended_versions(contract, repo_root=repo_root)
    if auto_version:
        if recommended_versions is None:
            raise ValueError("无法自动生成版本号；请确认 upstream version 与 git sha 可从应用仓库读取")
        effective_image_tag = str(recommended_versions["image_tag"])
    else:
        effective_image_tag = image_tag or "local"
    image_ref = f"{contract_spec.packaging.image_name}:{effective_image_tag}"
    command = contract_spec.artifact.build_command
    env = os.environ.copy()
    env["IMAGE_TAG"] = effective_image_tag
    env["ARTIFACT_OUTPUT_PATH"] = str(output_path)
    env["ARTIFACT_RUNTIME_OS"] = str(contract_spec.artifact.runtime_os)
    env["ARTIFACT_RUNTIME_ARCH"] = str(contract_spec.artifact.runtime_arch)
    if recommended_versions is not None:
        env["FORK_VERSION"] = str(recommended_versions["fork_version"])
        env["DELIVERY_VERSION"] = str(recommended_versions["delivery_version"])
    op_id = next_operation_id("build-artifact")
    artifact_payload = {
        "output_path": str(output_path),
        "runtime_os": contract_spec.artifact.runtime_os,
        "runtime_arch": contract_spec.artifact.runtime_arch,
    }
    packaging_payload = {
        "backend": contract_spec.packaging.backend,
        "image_ref": image_ref,
        "package_command": contract_spec.packaging.package_command,
    }
    details: dict[str, Any] = {
        "app_id": str(contract["app_id"]),
        "artifact_output_path": str(output_path),
        "image_ref": image_ref,
        "packaging_backend": contract_spec.packaging.backend,
    }
    if recommended_versions is not None:
        details.update(
            {
                "upstream_version": recommended_versions["upstream_version"],
                "fork_version_date": recommended_versions["build_date"],
                "fork_sequence": recommended_versions["fork_sequence"],
                "git_sha": recommended_versions["git_sha"],
                "fork_version": recommended_versions["fork_version"],
                "delivery_version": recommended_versions["delivery_version"],
                "image_tag": recommended_versions["image_tag"],
            }
        )
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="build-artifact",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "result": "planned"},
            details=details,
        )
        payload = {
            "artifact": artifact_payload,
            "packaging": packaging_payload,
            "cwd": str(app_root),
            "command": command,
            "dry_run": True,
            "operation": operation,
        }
        if recommended_versions is not None:
            payload["recommended_versions"] = recommended_versions
        return payload
    result = _run_linux_backend_command(
        command,
        cwd=app_root,
        env=env,
        backend=contract_spec.packaging.backend,
    )
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "build-artifact 执行失败")
    if not output_path.exists():
        raise ValueError(f"build-artifact 未生成预期 artifact 输出: {output_path}")
    operation = _record_app_operation(
        repo_root,
        action="build-artifact",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "result": "artifact-built"},
        details=details,
    )
    payload = {
        "artifact": artifact_payload,
        "packaging": packaging_payload,
        "cwd": str(app_root),
        "command": command,
        "operation": operation,
    }
    if recommended_versions is not None:
        payload["recommended_versions"] = recommended_versions
    return payload


def package_runtime(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
) -> dict[str, Any]:
    _record_app_operation, _, _run_linux_backend_command, _ = _get_runtime_helpers()

    contract_spec = require_artifact_first_contract(contract)
    app_root = Path(contract["_meta"]["app_root"])
    output_path = artifact_output_path(app_root, contract_spec)
    if output_path is None:
        raise ValueError("artifact-first 合同缺少 artifact.output_path")
    recommended_versions = _maybe_recommended_versions(contract, repo_root=repo_root)
    if auto_version:
        if recommended_versions is None:
            raise ValueError("无法自动生成版本号；请确认 upstream version 与 git sha 可从应用仓库读取")
        effective_image_tag = str(recommended_versions["image_tag"])
    else:
        effective_image_tag = image_tag or "local"
    image_ref = f"{contract_spec.packaging.image_name}:{effective_image_tag}"
    env = os.environ.copy()
    env["IMAGE_TAG"] = effective_image_tag
    env["IMAGE_REF"] = image_ref
    env["ARTIFACT_OUTPUT_PATH"] = str(output_path)
    env["ARTIFACT_RUNTIME_OS"] = str(contract_spec.artifact.runtime_os)
    env["ARTIFACT_RUNTIME_ARCH"] = str(contract_spec.artifact.runtime_arch)
    if recommended_versions is not None:
        env["FORK_VERSION"] = str(recommended_versions["fork_version"])
        env["DELIVERY_VERSION"] = str(recommended_versions["delivery_version"])
    op_id = next_operation_id("package-runtime")
    payload = {
        "artifact": {
            "output_path": str(output_path),
            "runtime_os": contract_spec.artifact.runtime_os,
            "runtime_arch": contract_spec.artifact.runtime_arch,
        },
        "image_ref": image_ref,
        "backend": contract_spec.packaging.backend,
        "cwd": str(app_root),
        "command": contract_spec.packaging.package_command,
    }
    details: dict[str, Any] = {
        "app_id": str(contract["app_id"]),
        "artifact_output_path": str(output_path),
        "image_ref": image_ref,
        "packaging_backend": contract_spec.packaging.backend,
    }
    if recommended_versions is not None:
        details["image_tag"] = recommended_versions["image_tag"]
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="package-runtime",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "result": "planned"},
            details=details,
        )
        payload["dry_run"] = True
        payload["operation"] = operation
        if recommended_versions is not None:
            payload["recommended_versions"] = recommended_versions
        return payload
    if not output_path.exists():
        raise ValueError(f"package-runtime 需要现成 artifact 输出: {output_path}")
    result = _run_linux_backend_command(
        contract_spec.packaging.package_command,
        cwd=app_root,
        env=env,
        backend=contract_spec.packaging.backend,
    )
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "package-runtime 执行失败")
    operation = _record_app_operation(
        repo_root,
        action="package-runtime",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "result": "packaged"},
        details=details,
    )
    payload["operation"] = operation
    if recommended_versions is not None:
        payload["recommended_versions"] = recommended_versions
    return payload


def ship_image(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_ref: str | None,
    archive_dir: Path,
    dry_run: bool,
    _streamer=stream_docker_image,
) -> dict[str, Any]:
    _record_app_operation, _, _, _target_ssh_target = _get_runtime_helpers()

    op_id = next_operation_id("ship-image")
    if not image_ref:
        raise ValueError("ship-image 必须显式传入 image_ref")
    effective_image = image_ref
    archive_path = (repo_root / archive_dir / f"{effective_image.replace(':', '_')}.tar").resolve()
    if target == "wsl":
        operation = _record_app_operation(
            repo_root,
            action="ship-image",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
            details={"artifact": archive_path.name, "image_ref": effective_image},
        )
        return {
            "image_ref": effective_image,
            "archive_path": str(archive_path),
            "target": target,
            "operation": operation,
            "dry_run": dry_run,
        }
    ssh_target = _target_ssh_target(repo_root, target)
    commands = {
        "stream": f"docker save {shlex.quote(effective_image)} | ssh {ssh_target.connection_target} docker load",
    }
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="ship-image",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "artifact": archive_path.name, "result": "planned"},
            details={"artifact": archive_path.name, "image_ref": effective_image},
        )
        return {
            "image_ref": effective_image,
            "archive_path": str(archive_path),
            "target": target,
            "commands": commands,
            "operation": operation,
            "dry_run": True,
        }

    result = _streamer(effective_image, ssh_target)
    if not result.ok:
        raise ValueError(result.stderr or "流式 docker 传输失败")
    operation = _record_app_operation(
        repo_root,
        action="ship-image",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "artifact": archive_path.name, "result": "loaded"},
        details={"artifact": archive_path.name, "image_ref": effective_image},
    )
    return {
        "image_ref": effective_image,
        "archive_path": str(archive_path),
        "target": target,
        "commands": commands,
        "operation": operation,
    }
