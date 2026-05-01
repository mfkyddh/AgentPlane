#!/usr/bin/env python3
"""Automate Cloudflare DNS + 1Panel website/certificate public ingress setup."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.adapters.cloudflare import CloudflareClient, load_shell_env_file
from agentplane.scripts.onepanel.client import load_config, send_signed_request
from agentplane.scripts.onepanel.env_targets import TargetConfig, build_api_request_command, get_target


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

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if self.target.mode == "local":
            config = load_config(Path(self.env_file_override) if self.env_file_override else self.target.api_env_file)
            response = send_signed_request(
                config,
                method,
                path,
                body_bytes=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
            )
        else:
            command = build_api_request_command(self.target, method, path, body=body)
            result = subprocess.run(
                self.target.build_ssh_target().local_ssh_args_for_argv(command),
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    result.stdout.strip() or result.stderr.strip() or f"1Panel request failed: {method} {path}"
                )
            response = json.loads(result.stdout)
        body_payload = response.get("body")
        if response.get("status", 500) >= 400 or not isinstance(body_payload, dict) or body_payload.get("code") != 200:
            raise RuntimeError(json.dumps(response, ensure_ascii=False))
        return body_payload.get("data")


class PublicIngressManager:
    def __init__(self, panel: OnePanelExecutor, cloudflare: CloudflareClient, config: PublicIngressConfig) -> None:
        self.panel = panel
        self.cloudflare = cloudflare
        self.config = config

    def ensure(self) -> dict[str, Any]:
        dns_result = self.cloudflare.ensure_dns_record(
            zone_name=self.config.zone_name,
            record_name=self.config.domain,
            record_type=self.config.record_type,
            content=self.config.record_content,
            proxied=self.config.record_proxied,
        )
        acme = self.ensure_acme_account()
        dns_account = self.ensure_dns_account()
        ssl = self.ensure_ssl(acme_id=int(acme["id"]), dns_account_id=int(dns_account["id"]))
        website = self.ensure_website()
        https = self.ensure_https_binding(website_id=int(website["id"]), ssl_id=int(ssl["id"]))
        return {
            "cloudflare_dns": {
                "action": dns_result["action"],
                "changed": dns_result["changed"],
                "record_name": self.config.domain,
                "record_type": self.config.record_type,
                "record_content": self.config.record_content,
                "proxied": self.config.record_proxied,
            },
            "acme_account": {
                "id": acme["id"],
                "email": acme["email"],
                "type": acme["type"],
            },
            "dns_account": {
                "id": dns_account["id"],
                "name": dns_account["name"],
                "type": dns_account["type"],
            },
            "ssl": {
                "id": ssl["id"],
                "domain": ssl["primaryDomain"],
                "status": ssl["status"],
                "dir": ssl["dir"],
                "autoRenew": ssl["autoRenew"],
            },
            "ingress": {
                "id": website["id"],
                "alias": website["alias"],
                "primaryDomain": website["primaryDomain"],
                "status": website["status"],
                "proxy": website.get("proxy"),
            },
            "https": {
                "enable": https["enable"],
                "httpConfig": https["httpConfig"],
                "httpsPort": https.get("httpsPort"),
                "sslId": https["SSL"]["id"],
            },
        }

    def _page_items(self, path: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        payload = self.panel.request("POST", path, body)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected paginated payload for {path}: {json.dumps(payload, ensure_ascii=False)}")
        items = payload.get("items")
        if items is None and payload.get("total") == 0:
            return []
        if not isinstance(items, list):
            raise RuntimeError(f"Unexpected paginated payload for {path}: {json.dumps(payload, ensure_ascii=False)}")
        return items

    def find_acme_account(self) -> dict[str, Any] | None:
        items = self._page_items("/api/v2/websites/acme/search", {"page": 1, "pageSize": 100})
        for item in items:
            if item.get("email") == self.config.acme_email and item.get("type") == self.config.acme_type:
                return item
        return None

    def ensure_acme_account(self) -> dict[str, Any]:
        existing = self.find_acme_account()
        if existing is not None:
            return existing
        self.panel.request(
            "POST",
            "/api/v2/websites/acme",
            {
                "email": self.config.acme_email,
                "type": self.config.acme_type,
                "keyType": self.config.acme_key_type,
                "useProxy": False,
                "useEAB": False,
            },
        )
        existing = self.find_acme_account()
        if existing is not None:
            return existing
        raise RuntimeError(f"ACME account not found after create: {self.config.acme_email}")

    def find_dns_account(self) -> dict[str, Any] | None:
        items = self._page_items("/api/v2/websites/dns/search", {"page": 1, "pageSize": 100})
        for item in items:
            if (
                item.get("name") == self.config.dns_account_name
                and item.get("type") == self.config.dns_account_provider
            ):
                return item
        return None

    def ensure_dns_account(self) -> dict[str, Any]:
        existing = self.find_dns_account()
        if existing is not None:
            return existing
        self.panel.request(
            "POST",
            "/api/v2/websites/dns",
            {
                "name": self.config.dns_account_name,
                "type": self.config.dns_account_provider,
                "authorization": {
                    "email": self.config.dns_account_email,
                    "apiKey": self.cloudflare.token,
                },
            },
        )
        existing = self.find_dns_account()
        if existing is not None:
            return existing
        raise RuntimeError(f"DNS account not found after create: {self.config.dns_account_name}")

    def find_ssl(self) -> dict[str, Any] | None:
        items = self._page_items(
            "/api/v2/websites/ssl/search",
            {
                "page": 1,
                "pageSize": 100,
                "domain": self.config.cert_primary_domain,
                "acmeAccountID": "",
                "orderBy": "created_at",
                "order": "descending",
            },
        )
        for item in items:
            if item.get("primaryDomain") == self.config.cert_primary_domain:
                return item
        return None

    def ensure_ssl(self, *, acme_id: int, dns_account_id: int) -> dict[str, Any]:
        existing = self.find_ssl()
        if existing is None:
            created = self.panel.request(
                "POST",
                "/api/v2/websites/ssl",
                {
                    "primaryDomain": self.config.cert_primary_domain,
                    "otherDomains": self.config.cert_other_domains,
                    "provider": "dnsAccount",
                    "acmeAccountId": acme_id,
                    "dnsAccountId": dns_account_id,
                    "autoRenew": self.config.cert_auto_renew,
                    "keyType": self.config.cert_key_type,
                    "apply": False,
                    "pushDir": True,
                    "dir": self.config.cert_dir,
                    "description": self.config.cert_description,
                    "disableCNAME": False,
                    "skipDNS": False,
                    "execShell": True,
                    "shell": self.config.cert_reload_shell,
                    "pushNode": False,
                    "nodes": "",
                    "isIp": False,
                },
            )
            ssl_id = int(created.get("id", 0)) if isinstance(created, dict) else 0
            if ssl_id:
                existing = self.panel.request("GET", f"/api/v2/websites/ssl/{ssl_id}")
            else:
                existing = self.wait_for_ssl_search()
        if existing.get("status") != "ready":
            self.panel.request(
                "POST",
                "/api/v2/websites/ssl/obtain",
                {"ID": int(existing["id"]), "skipDNSCheck": False, "nameservers": [], "disableLog": False},
            )
            existing = self.wait_for_ssl_ready(int(existing["id"]))
        return existing

    def wait_for_ssl_search(self, timeout_seconds: int = 120) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            existing = self.find_ssl()
            if existing is not None:
                return existing
            time.sleep(2)
        raise TimeoutError(f"Timed out waiting for SSL row: {self.config.cert_primary_domain}")

    def wait_for_ssl_ready(self, ssl_id: int, timeout_seconds: int = 600) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            payload = self.panel.request("GET", f"/api/v2/websites/ssl/{ssl_id}")
            status = payload.get("status")
            if status == "ready":
                return payload
            if status == "applyError":
                raise RuntimeError(f"SSL obtain failed for {self.config.cert_primary_domain}")
            time.sleep(5)
        raise TimeoutError(f"Timed out waiting for SSL ready: {self.config.cert_primary_domain}")

    def _search_ingresses(self) -> list[dict[str, Any]]:
        return self._page_items(
            "/api/v2/websites/search",
            {
                "page": 1,
                "pageSize": 100,
                "name": "",
                "websiteGroupId": 0,
                "orderBy": "created_at",
                "order": "descending",
            },
        )

    def find_website(self) -> dict[str, Any] | None:
        for item in self._search_ingresses():
            if item.get("primaryDomain") == self.config.domain or item.get("alias") == self.config.website_alias:
                return item
        return None

    def ensure_website(self) -> dict[str, Any]:
        existing = self.find_website()
        if existing is not None:
            return existing
        self.panel.request(
            "POST",
            "/api/v2/websites",
            {
                "alias": self.config.website_alias,
                "type": self.config.website_type,
                # 1Panel v2 expects AppType to describe whether this is a fresh
                # website or an installed app, not the website proxy/static type.
                "appType": "new",
                "remark": self.config.website_remark,
                "proxy": self.config.website_proxy,
                "webSiteGroupID": self.config.website_group_id,
                "IPV6": self.config.website_ipv6,
                "domains": [{"domain": self.config.domain, "port": 80, "ssl": False}],
            },
        )
        existing = self.find_website()
        if existing is not None:
            return existing
        raise RuntimeError(f"Website not found after create: {self.config.domain}")

    def ensure_https_binding(self, *, website_id: int, ssl_id: int) -> dict[str, Any]:
        current = self.panel.request("GET", f"/api/v2/websites/{website_id}/https")
        current_ssl = current.get("SSL", {}) if isinstance(current, dict) else {}
        https_port = str(self.config.https_ports[0]) if self.config.https_ports else ""
        if (
            current.get("enable") is True
            and current.get("httpConfig") == self.config.https_http_config
            and int(current_ssl.get("id", 0)) == ssl_id
            and str(current.get("httpsPort", https_port)) == https_port
        ):
            return current
        self.panel.request(
            "POST",
            f"/api/v2/websites/{website_id}/https",
            {
                "websiteId": website_id,
                "enable": True,
                "type": "existed",
                "websiteSSLId": ssl_id,
                "httpConfig": self.config.https_http_config,
                "httpsPorts": self.config.https_ports,
            },
        )
        return self.panel.request("GET", f"/api/v2/websites/{website_id}/https")

    def verify(self) -> dict[str, Any]:
        dns_record = self.cloudflare.find_dns_record(
            zone_name=self.config.zone_name,
            record_name=self.config.domain,
            record_type=self.config.record_type,
        )
        acme = self.find_acme_account()
        dns_account = self.find_dns_account()
        ssl = self.find_ssl()
        website = self.find_website()
        https = (
            self.panel.request("GET", f"/api/v2/websites/{int(website['id'])}/https") if website is not None else None
        )
        https_port = str(self.config.https_ports[0]) if self.config.https_ports else ""
        actual_ssl = https.get("SSL", {}) if isinstance(https, dict) else {}

        checks: dict[str, dict[str, Any]] = {
            "dns_exists": {"ok": dns_record is not None},
            "dns_content": {
                "ok": isinstance(dns_record, dict) and dns_record.get("content") == self.config.record_content,
                "actual": dns_record.get("content") if isinstance(dns_record, dict) else None,
                "expected": self.config.record_content,
            },
            "dns_proxied": {
                "ok": isinstance(dns_record, dict) and bool(dns_record.get("proxied")) == self.config.record_proxied,
                "actual": bool(dns_record.get("proxied")) if isinstance(dns_record, dict) else None,
                "expected": self.config.record_proxied,
            },
            "acme_account": {"ok": acme is not None},
            "dns_account": {"ok": dns_account is not None},
            "ssl": {"ok": ssl is not None},
            "ssl_status": {
                "ok": isinstance(ssl, dict) and ssl.get("status") == "ready",
                "actual": ssl.get("status") if isinstance(ssl, dict) else None,
                "expected": "ready",
            },
            "ingress": {"ok": website is not None},
            "website_alias": {
                "ok": isinstance(website, dict) and website.get("alias") == self.config.website_alias,
                "actual": website.get("alias") if isinstance(website, dict) else None,
                "expected": self.config.website_alias,
            },
            "website_domain": {
                "ok": isinstance(website, dict) and website.get("primaryDomain") == self.config.domain,
                "actual": website.get("primaryDomain") if isinstance(website, dict) else None,
                "expected": self.config.domain,
            },
            "website_proxy": {
                "ok": isinstance(website, dict) and website.get("proxy") == self.config.website_proxy,
                "actual": website.get("proxy") if isinstance(website, dict) else None,
                "expected": self.config.website_proxy,
            },
            "https_enabled": {
                "ok": isinstance(https, dict) and bool(https.get("enable")),
                "actual": bool(https.get("enable")) if isinstance(https, dict) else None,
                "expected": True,
            },
            "https_http_config": {
                "ok": isinstance(https, dict) and https.get("httpConfig") == self.config.https_http_config,
                "actual": https.get("httpConfig") if isinstance(https, dict) else None,
                "expected": self.config.https_http_config,
            },
            "https_port": {
                "ok": isinstance(https, dict) and str(https.get("httpsPort", https_port)) == https_port,
                "actual": str(https.get("httpsPort", "")) if isinstance(https, dict) else None,
                "expected": https_port,
            },
            "https_ssl_id": {
                "ok": isinstance(ssl, dict)
                and isinstance(https, dict)
                and int(actual_ssl.get("id", 0)) == int(ssl.get("id", 0)),
                "actual": actual_ssl.get("id") if isinstance(actual_ssl, dict) else None,
                "expected": ssl.get("id") if isinstance(ssl, dict) else None,
            },
        }
        failures = [name for name, item in checks.items() if not bool(item.get("ok"))]
        return {
            "ok": not failures,
            "domain": self.config.domain,
            "zone": self.config.zone_name,
            "website_alias": self.config.website_alias,
            "checks": checks,
            "failures": failures,
            "evidence": {
                "dns_record": dns_record or {"found": False},
                "acme_account": acme or {"found": False},
                "dns_account": dns_account or {"found": False},
                "ssl": ssl or {"found": False},
                "ingress": website or {"found": False},
                "https": https or {"found": False},
            },
        }


def _build_manager(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> tuple[PublicIngressConfig, dict[str, str], CloudflareClient, PublicIngressManager]:
    ingress_config = PublicIngressConfig.from_env_file(config_file)
    cloudflare_env = load_shell_env_file(cloudflare_env_file)
    panel = OnePanelExecutor(get_target(env, env_file), env_file_override=env_file)
    cloudflare = CloudflareClient(cloudflare_env["CLOUDFLARE_API_TOKEN"])
    manager = PublicIngressManager(panel=panel, cloudflare=cloudflare, config=ingress_config)
    return ingress_config, cloudflare_env, cloudflare, manager


def plan_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, _cloudflare, _manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    return {
        "ok": True,
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "website_alias": ingress_config.website_alias,
        "config_file": str(config_file.resolve()),
        "cloudflare_env_file": str(cloudflare_env_file.resolve()),
        "cloudflare_account_id": cloudflare_env.get("CLOUDFLARE_ACCOUNT_ID", ""),
        "execute_required": True,
        "steps": [
            {
                "kind": "cloudflare_dns",
                "action": "ensure",
                "record_name": ingress_config.domain,
                "record_type": ingress_config.record_type,
                "record_content": ingress_config.record_content,
                "proxied": ingress_config.record_proxied,
            },
            {
                "kind": "onepanel_acme",
                "action": "ensure",
                "email": ingress_config.acme_email,
                "type": ingress_config.acme_type,
            },
            {
                "kind": "onepanel_dns_account",
                "action": "ensure",
                "name": ingress_config.dns_account_name,
                "type": ingress_config.dns_account_provider,
            },
            {"kind": "onepanel_ssl", "action": "ensure", "primary_domain": ingress_config.cert_primary_domain},
            {
                "kind": "onepanel_website",
                "action": "ensure",
                "alias": ingress_config.website_alias,
                "proxy": ingress_config.website_proxy,
            },
            {"kind": "onepanel_https", "action": "ensure", "https_ports": ingress_config.https_ports},
        ],
    }


def verify_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, cloudflare, manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    cloudflare.verify_account_token(cloudflare_env["CLOUDFLARE_ACCOUNT_ID"])
    payload = manager.verify()
    return {
        "command": "onepanel public-ingress verify",
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "payload": payload,
    }


def ensure_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, cloudflare, manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    cloudflare.verify_account_token(cloudflare_env["CLOUDFLARE_ACCOUNT_ID"])
    payload = manager.ensure()
    return {
        "command": "onepanel public-ingress ensure",
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "payload": payload,
    }


def command_ensure_public_ingress(args: argparse.Namespace) -> dict[str, Any]:
    return ensure_public_ingress(
        args.env,
        Path(args.config_file),
        Path(args.cloudflare_env_file),
        env_file=args.env_file,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure public ingress through Cloudflare and 1Panel.")
    parser.add_argument("--env", required=True, help="1Panel target environment")
    parser.add_argument("--env-file", help="Override 1Panel API env file")
    parser.add_argument("--config-file", required=True, help="Public ingress env-style config file")
    parser.add_argument("--cloudflare-env-file", required=True, help="Shell env file with Cloudflare token")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = command_ensure_public_ingress(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
