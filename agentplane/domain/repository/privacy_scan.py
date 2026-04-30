from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agentplane.domain.repository.secret_scan import SecretScanAllow, load_secret_scan_allowlist

PRIVATE_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-inventory", re.compile(r"^inventory/servers/")),
    ("private-state-snapshot", re.compile(r"^inventory/state-snapshot\.md$")),
    ("private-runbook", re.compile(r"^docs/runbooks/(prod\d+-|wsl-secrets-backup|wsl-zzz-skills-sync)")),
    ("private-archive-runbook", re.compile(r"^docs/archive/runbooks/prod\d+-")),
    ("private-compose-target", re.compile(r"^infra/compose/.+/docker-compose\.prod\d+\.ya?ml$")),
    ("private-compose-service", re.compile(r"^infra/compose/(relay-trojan|vmail)/")),
    ("private-skill", re.compile(r"^\.agents/skills/(tencent-|nginxui-letsencrypt|windows-mihomo)")),
    ("private-host-helper", re.compile(r"^agentplane/(cli/prod0_|scripts/probe/probe_tencent|scripts/remote/remote_.*prod0)")),
    ("private-prod-env-example", re.compile(r"^templates/services/.+\.prod\d+\.env\.example$")),
)

PRIVATE_CONTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-domain", re.compile(r"\b(?:[\w-]+\.)?" + "zzzai" + r"\.(?:cloud|fun)\b", re.IGNORECASE)),
    ("private-public-ip", re.compile(r"\b(?:175\.178\.114\.\d+|38\.12\.32\.\d+)\b")),
    (
        "private-panel-entrance",
        re.compile(
            r"\b(?:" + "safe" + r"_entrance|p2" + r"panel443|0f0e" + r"8602e3)\b",
            re.IGNORECASE,
        ),
    ),
    ("private-cloud-provider", re.compile(r"\bTencent" + r" Cloud\b|朝" + r"晞云", re.IGNORECASE)),
    ("private-password-ssh", re.compile(r'"password_authentication"\s*:\s*true', re.IGNORECASE)),
    ("private-root-ssh", re.compile(r'"permit_root_login"\s*:\s*true', re.IGNORECASE)),
)


@dataclass(frozen=True)
class PrivacyScanIssue:
    path: str
    kind: str
    line: int | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "line": self.line,
            "detail": self.detail,
        }


def _git_visible_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [repo_root / line for line in result.stdout.splitlines() if line.strip()]


def _is_text_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in chunk


def _scan_path(relative: str) -> list[PrivacyScanIssue]:
    issues: list[PrivacyScanIssue] = []
    for kind, pattern in PRIVATE_PATH_PATTERNS:
        if pattern.search(relative):
            issues.append(
                PrivacyScanIssue(
                    path=relative,
                    kind=kind,
                    line=None,
                    detail="private control-plane state must remain ignored and out of public Git",
                )
            )
    return issues


def _scan_content(repo_root: Path, path: Path) -> list[PrivacyScanIssue]:
    if not path.is_file() or not _is_text_file(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    relative = path.relative_to(repo_root).as_posix()
    issues: list[PrivacyScanIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PRIVATE_CONTENT_PATTERNS:
            if not pattern.search(line):
                continue
            issues.append(
                PrivacyScanIssue(
                    path=relative,
                    kind=kind,
                    line=line_number,
                    detail="public files must use placeholders or RFC 5737/example domains instead of maintainer-local facts",
                )
            )
    return issues


def scan_repository_for_private_material(
    repo_root: Path, allowlist_path: Path | None = None
) -> list[PrivacyScanIssue]:
    root = repo_root.resolve()
    allowlist = load_secret_scan_allowlist(root, allowlist_path)
    issues: list[PrivacyScanIssue] = []
    for path in _git_visible_files(root):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        issues.extend(_scan_path(relative))
        issues.extend(_scan_content(root, path))
    return [issue for issue in issues if not any(a.matches(issue) for a in allowlist)]
