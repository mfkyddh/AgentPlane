from __future__ import annotations

import json
import time
from typing import Any

from agentplane.adapters.cloudflare import CloudflareClient
from agentplane.scripts.onepanel.public_ingress_config import OnePanelExecutor, PublicIngressConfig


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
