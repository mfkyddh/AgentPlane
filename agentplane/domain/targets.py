from __future__ import annotations

FORMAL_TARGETS: tuple[str, ...] = ("wsl", "prod0-main", "prod2-main")
PRODUCTION_TARGETS: tuple[str, ...] = ("prod0-main", "prod2-main")

TARGET_ALIASES: dict[str, str] = {
    "wsl": "wsl",
    "prod0-main": "prod0",
    "prod2-main": "prod2",
}

SUPPORTED_APP_TARGETS = FORMAL_TARGETS
SUPPORTED_SERVICE_TARGETS = FORMAL_TARGETS
SUPPORTED_INGRESS_TARGETS = FORMAL_TARGETS
SUPPORTED_RUNTIME_ENV_TARGETS = FORMAL_TARGETS
SUPPORTED_INFRA_TARGETS = FORMAL_TARGETS


def is_production_target(target: str) -> bool:
    return target in PRODUCTION_TARGETS


def target_alias(target: str) -> str:
    try:
        return TARGET_ALIASES[target]
    except KeyError as exc:
        raise ValueError(f"unsupported target alias: {target}") from exc


def remote_compose_filename(target: str) -> str:
    return f"docker-compose.{target_alias(target)}.yml"
