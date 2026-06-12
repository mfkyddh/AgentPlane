from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.adapters.cloudflare import load_shell_env_file
from agentplane.scripts.onepanel.env_targets import TargetConfig
from agentplane.scripts.onepanel.executor import TargetExecutor


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int_list(value: str | None) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for item in value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        result.append(int(stripped))
    return result


@dataclass(frozen=True)
class PublicIngressConfig:
    domain: str
    zone_name: str
    record_type: str
    record_content: str
    record_proxied: bool
    dns_account_name: str
    dns_account_provider: str
    dns_account_email: str
    acme_email: str
    acme_type: str
    acme_key_type: str
    website_alias: str
    website_type: str
    website_group_id: int
    website_proxy: str
    website_remark: str
    website_ipv6: bool
    cert_primary_domain: str
    cert_other_domains: str
    cert_dir: str
    cert_description: str
    cert_key_type: str
    cert_auto_renew: bool
    cert_reload_shell: str
    https_http_config: str
    https_ports: list[int]

    @classmethod
    def from_env_file(cls, path: Path) -> "PublicIngressConfig":
        env = load_shell_env_file(path)
        return cls(
            domain=env["PUBLIC_INGRESS_DOMAIN"],
            zone_name=env["PUBLIC_INGRESS_ZONE_NAME"],
            record_type=env.get("PUBLIC_INGRESS_RECORD_TYPE", "A"),
            record_content=env["PUBLIC_INGRESS_RECORD_CONTENT"],
            record_proxied=parse_bool(env.get("PUBLIC_INGRESS_RECORD_PROXIED"), default=True),
            dns_account_name=env["ONEPANEL_DNS_ACCOUNT_NAME"],
            dns_account_provider=env.get("ONEPANEL_DNS_ACCOUNT_PROVIDER", "CloudFlare"),
            dns_account_email=env["ONEPANEL_DNS_ACCOUNT_EMAIL"],
            acme_email=env.get("ONEPANEL_ACME_EMAIL", "acme@1paneldev.com"),
            acme_type=env.get("ONEPANEL_ACME_TYPE", "letsencrypt"),
            acme_key_type=env.get("ONEPANEL_ACME_KEY_TYPE", "2048"),
            website_alias=env["ONEPANEL_WEBSITE_ALIAS"],
            website_type=env.get("ONEPANEL_WEBSITE_TYPE", "proxy"),
            website_group_id=int(env.get("ONEPANEL_WEBSITE_GROUP_ID", "1")),
            website_proxy=env["ONEPANEL_WEBSITE_PROXY"],
            website_remark=env.get("ONEPANEL_WEBSITE_REMARK", ""),
            website_ipv6=parse_bool(env.get("ONEPANEL_WEBSITE_IPV6"), default=True),
            cert_primary_domain=env.get("ONEPANEL_CERT_PRIMARY_DOMAIN", env["PUBLIC_INGRESS_DOMAIN"]),
            cert_other_domains=env.get("ONEPANEL_CERT_OTHER_DOMAINS", ""),
            cert_dir=env["ONEPANEL_CERT_DIR"],
            cert_description=env.get("ONEPANEL_CERT_DESCRIPTION", ""),
            cert_key_type=env.get("ONEPANEL_CERT_KEY_TYPE", "2048"),
            cert_auto_renew=parse_bool(env.get("ONEPANEL_CERT_AUTO_RENEW"), default=True),
            cert_reload_shell=env["ONEPANEL_CERT_RELOAD_SHELL"],
            https_http_config=env.get("ONEPANEL_HTTPS_HTTP_CONFIG", "HTTPAlso"),
            https_ports=parse_int_list(env.get("ONEPANEL_HTTPS_PORTS", "443")),
        )


class OnePanelExecutor:
    def __init__(self, target: TargetConfig, env_file_override: str | None = None) -> None:
        self.target = target
        self.env_file_override = env_file_override
        self._delegate = TargetExecutor(target)

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        return self._delegate.api_request(method, path, body)
