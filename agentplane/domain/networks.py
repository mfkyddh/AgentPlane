from __future__ import annotations

import ipaddress
import json
import shlex
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

from agentplane.runtime.execution import CommandRunner
from agentplane.ssh import resolve_ssh_target


SUPPORTED_NETWORK_TARGETS = ("prod0-main", "prod2-main")


def managed_bridge_network_declaration_errors(inventory: dict[str, Any]) -> list[str]:
    raw = inventory.get("managed_bridge_networks")
    if not isinstance(raw, list) or not raw:
        return ["managed_bridge_networks must be a non-empty list"]

    errors: list[str] = []
    for index, item in enumerate(raw):
        prefix = f"managed_bridge_networks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("name", "driver", "subnet", "gateway_ip"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        driver = item.get("driver")
        if isinstance(driver, str) and driver != "bridge":
            errors.append(f"{prefix}.driver only supports bridge")
        required_for = item.get("required_for", [])
        if required_for is not None and (
            not isinstance(required_for, list) or any(not isinstance(entry, str) or not entry.strip() for entry in required_for)
        ):
            errors.append(f"{prefix}.required_for must be a string list")
        subnet = item.get("subnet")
        gateway_ip = item.get("gateway_ip")
        try:
            subnet_network = ipaddress.ip_network(str(subnet), strict=True)
        except ValueError:
            errors.append(f"{prefix}.subnet must be a valid CIDR network")
            subnet_network = None
        try:
            gateway_interface = ipaddress.ip_interface(str(gateway_ip))
        except ValueError:
            errors.append(f"{prefix}.gateway_ip must be a valid CIDR interface")
            gateway_interface = None
        if subnet_network is not None and gateway_interface is not None and gateway_interface.network != subnet_network:
            errors.append(f"{prefix}.gateway_ip must belong to {subnet_network}")
    return errors


def _load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def _normalized_managed_bridge_networks(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    errors = managed_bridge_network_declaration_errors(inventory)
    if errors:
        raise ValueError("; ".join(errors))
    raw = inventory["managed_bridge_networks"]
    normalized: list[dict[str, Any]] = []
    for item in raw:
        gateway_interface = ipaddress.ip_interface(str(item["gateway_ip"]))
        normalized.append(
            {
                "name": str(item["name"]),
                "driver": "bridge",
                "subnet": str(item["subnet"]),
                "gateway_ip": str(item["gateway_ip"]),
                "gateway_addr": str(gateway_interface.ip),
                "required_for": list(item.get("required_for", [])),
            }
        )
    return normalized


def _run(command: list[str]) -> CompletedProcess[str]:
    return CommandRunner().run(command)


def _execute_step(*, argv: list[str], display: str) -> dict[str, Any]:
    result = _run(argv)
    return {
        "argv": argv,
        "display": display,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ok": result.returncode == 0,
    }


def _remote_step(repo_root: Path, target: str, command: str) -> dict[str, Any]:
    ssh_target = resolve_ssh_target(repo_root, target)
    return _execute_step(
        argv=ssh_target.ssh_args_for_shell(command),
        display=ssh_target.display_ssh_command(command),
    )


def _bridge_interface_name(network_payload: dict[str, Any]) -> str | None:
    options = network_payload.get("Options")
    if isinstance(options, dict):
        bridge_name = options.get("com.docker.network.bridge.name")
        if isinstance(bridge_name, str) and bridge_name:
            return bridge_name
    network_id = network_payload.get("Id")
    if isinstance(network_id, str) and len(network_id) >= 12:
        return f"br-{network_id[:12]}"
    return None


def _parse_json_output(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    return json.loads(text)


def _connected_container_names(inspect_payload: dict[str, Any]) -> list[str]:
    containers = inspect_payload.get("Containers")
    if not isinstance(containers, dict):
        return []
    names: list[str] = []
    for item in containers.values():
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        if isinstance(name, str) and name:
            names.append(name)
    return sorted(set(names))


def _network_state(repo_root: Path, target: str, declaration: dict[str, Any]) -> dict[str, Any]:
    inspect_step = _remote_step(
        repo_root,
        target,
        f"docker network inspect {shlex.quote(declaration['name'])} --format '{{{{json .}}}}'",
    )
    bridge_interface: str | None = None
    driver_matches = False
    subnet_matches = False
    docker_gateway_matches = False
    bridge_interface_exists = False
    gateway_ip_present = False
    route_present = False
    required_containers_present = False
    connected_containers: list[str] = []
    missing_required_containers = list(declaration["required_for"])
    problems: list[str] = []

    if not inspect_step["ok"]:
        problems.append("network_missing")
        return {
            "name": declaration["name"],
            "driver": declaration["driver"],
            "subnet": declaration["subnet"],
            "gateway_ip": declaration["gateway_ip"],
            "required_for": declaration["required_for"],
            "bridge_interface": None,
            "connected_containers": connected_containers,
            "missing_required_containers": missing_required_containers,
            "checks": {
                "network_exists": False,
                "driver_matches": False,
                "subnet_matches": False,
                "docker_gateway_matches": False,
                "bridge_interface_exists": False,
                "gateway_ip_present": False,
                "route_present": False,
                "required_containers_present": False,
            },
            "problems": problems,
        }

    inspect_payload = _parse_json_output(inspect_step["stdout"])
    if not isinstance(inspect_payload, dict):
        raise ValueError(f"无法解析 docker network inspect 输出: {declaration['name']}")

    connected_containers = _connected_container_names(inspect_payload)
    required_containers = list(declaration["required_for"])
    missing_required_containers = sorted(set(required_containers) - set(connected_containers))
    required_containers_present = not missing_required_containers

    bridge_interface = _bridge_interface_name(inspect_payload)
    driver_matches = inspect_payload.get("Driver") == declaration["driver"]
    ipam = inspect_payload.get("IPAM")
    if isinstance(ipam, dict):
        configs = ipam.get("Config")
        if isinstance(configs, list) and configs:
            first = configs[0] if isinstance(configs[0], dict) else {}
            subnet_matches = first.get("Subnet") == declaration["subnet"]
            docker_gateway_matches = first.get("Gateway") == declaration["gateway_addr"]

    if not driver_matches:
        problems.append("driver_mismatch")
    if not subnet_matches:
        problems.append("subnet_mismatch")
    if not docker_gateway_matches:
        problems.append("docker_gateway_mismatch")

    if bridge_interface:
        addr_step = _remote_step(repo_root, target, f"ip -json -4 addr show dev {shlex.quote(bridge_interface)}")
        bridge_interface_exists = addr_step["ok"]
        if bridge_interface_exists:
            addr_payload = _parse_json_output(addr_step["stdout"])
            if isinstance(addr_payload, list) and addr_payload:
                addr_info = addr_payload[0].get("addr_info")
                if isinstance(addr_info, list):
                    for addr in addr_info:
                        if not isinstance(addr, dict):
                            continue
                        local = addr.get("local")
                        prefixlen = addr.get("prefixlen")
                        if f"{local}/{prefixlen}" == declaration["gateway_ip"]:
                            gateway_ip_present = True
                            break

        route_step = _remote_step(repo_root, target, f"ip -json route show {shlex.quote(declaration['subnet'])}")
        if route_step["ok"]:
            route_payload = _parse_json_output(route_step["stdout"])
            if isinstance(route_payload, list) and route_payload:
                for route in route_payload:
                    if not isinstance(route, dict):
                        continue
                    if route.get("dst") == declaration["subnet"] and route.get("dev") == bridge_interface:
                        route_present = True
                        break

    if not bridge_interface_exists:
        problems.append("bridge_interface_missing")
    if not gateway_ip_present:
        problems.append("gateway_ip_missing")
    if not route_present:
        problems.append("route_missing")
    return {
        "name": declaration["name"],
        "driver": declaration["driver"],
        "subnet": declaration["subnet"],
        "gateway_ip": declaration["gateway_ip"],
        "required_for": declaration["required_for"],
        "bridge_interface": bridge_interface,
        "connected_containers": connected_containers,
        "missing_required_containers": missing_required_containers,
        "checks": {
            "network_exists": True,
            "driver_matches": driver_matches,
            "subnet_matches": subnet_matches,
            "docker_gateway_matches": docker_gateway_matches,
            "bridge_interface_exists": bridge_interface_exists,
            "gateway_ip_present": gateway_ip_present,
            "route_present": route_present,
            "required_containers_present": required_containers_present,
        },
        "problems": problems,
    }


def audit_managed_bridge_networks(repo_root: Path, target: str) -> dict[str, Any]:
    _, inventory = _load_inventory(repo_root, target)
    declarations = _normalized_managed_bridge_networks(inventory)
    networks = [_network_state(repo_root, target, declaration) for declaration in declarations]
    return {"ok": all(not item["problems"] for item in networks), "networks": networks}


def ensure_managed_bridge_networks(repo_root: Path, target: str) -> dict[str, Any]:
    _, inventory = _load_inventory(repo_root, target)
    declarations = _normalized_managed_bridge_networks(inventory)
    repairs: list[dict[str, Any]] = []

    for declaration in declarations:
        initial = _network_state(repo_root, target, declaration)
        bridge_interface = initial["bridge_interface"]

        if "network_missing" in initial["problems"]:
            create_step = _remote_step(
                repo_root,
                target,
                f"docker network create --driver bridge --subnet {shlex.quote(declaration['subnet'])} --gateway {shlex.quote(declaration['gateway_addr'])} {shlex.quote(declaration['name'])}",
            )
            repairs.append({"network": declaration["name"], "action": "create_network", **create_step})
            if not create_step["ok"]:
                return {"ok": False, "networks": [initial], "repairs": repairs}
            initial = _network_state(repo_root, target, declaration)
            bridge_interface = initial["bridge_interface"]

        if not initial["checks"]["driver_matches"] or not initial["checks"]["subnet_matches"]:
            return {"ok": False, "networks": [initial], "repairs": repairs}
        if not isinstance(bridge_interface, str) or not bridge_interface:
            return {"ok": False, "networks": [initial], "repairs": repairs}

        if not initial["checks"]["gateway_ip_present"]:
            addr_step = _remote_step(
                repo_root,
                target,
                f"ip addr add {shlex.quote(declaration['gateway_ip'])} dev {shlex.quote(bridge_interface)}",
            )
            repairs.append({"network": declaration["name"], "action": "add_gateway_ip", **addr_step})
            if not addr_step["ok"]:
                return {"ok": False, "networks": [initial], "repairs": repairs}

        if not initial["checks"]["route_present"]:
            route_step = _remote_step(
                repo_root,
                target,
                f"ip route replace {shlex.quote(declaration['subnet'])} dev {shlex.quote(bridge_interface)} src {shlex.quote(declaration['gateway_addr'])}",
            )
            repairs.append({"network": declaration["name"], "action": "replace_route", **route_step})
            if not route_step["ok"]:
                return {"ok": False, "networks": [initial], "repairs": repairs}

    final_state = audit_managed_bridge_networks(repo_root, target)
    final_state["repairs"] = repairs
    return final_state
