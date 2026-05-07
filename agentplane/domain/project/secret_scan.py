from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SENSITIVE_EXTENSIONS = {".key", ".pem", ".p12", ".crt"}
SENSITIVE_PATH_PARTS = {"secrets"}
CONFIG_SUFFIXES = {".conf", ".env", ".ini", ".toml", ".yaml", ".yml"}
PLACEHOLDER_WORDS = {
    "changeme",
    "demo",
    "dummy",
    "example",
    "placeholder",
    "replace",
    "sample",
    "test",
    "todo",
    "your",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai-token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "secret-assignment",
        re.compile(
            r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)\b"
            r"\s*[:=]\s*['\"]?([^'\"\s#]+)"
        ),
    ),
)


@dataclass(frozen=True)
class SecretScanIssue:
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


@dataclass(frozen=True)
class SecretScanAllow:
    kind: str
    path: str
    line: int | None = None

    def matches(self, issue: SecretScanIssue) -> bool:
        if self.kind not in {"*", issue.kind}:
            return False
        if self.path not in {"*", issue.path}:
            return False
        return self.line is None or self.line == issue.line


def load_secret_scan_allowlist(repo_root: Path, allowlist_path: Path | None = None) -> list[SecretScanAllow]:
    path = allowlist_path or repo_root / ".secret-scan-allowlist"
    if not path.is_file():
        return []

    allows: list[SecretScanAllow] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) not in {2, 3}:
            raise ValueError(f"invalid secret scan allowlist entry at {path}:{line_number}")
        allowed_line = int(parts[2]) if len(parts) == 3 else None
        allows.append(SecretScanAllow(kind=parts[0], path=parts[1], line=allowed_line))
    return allows


def _apply_allowlist(issues: list[SecretScanIssue], allowlist: list[SecretScanAllow]) -> list[SecretScanIssue]:
    return [issue for issue in issues if not any(allowed.matches(issue) for allowed in allowlist)]


def _git_files(repo_root: Path) -> list[Path]:
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


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'\"").lower()
    if not normalized:
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    if normalized.startswith("$"):
        return True
    if set(normalized) <= {"x", "*"}:
        return True
    return any(word in normalized for word in PLACEHOLDER_WORDS)


def _is_text_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in chunk


def _scan_file_content(repo_root: Path, path: Path) -> list[SecretScanIssue]:
    if not _is_text_file(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    relative = path.relative_to(repo_root).as_posix()
    scan_generic_assignments = (
        path.suffix.lower() in CONFIG_SUFFIXES
        or ".env" in path.name
        or relative.startswith("templates/")
        or relative.startswith("infra/compose/")
    )
    issues: list[SecretScanIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            if kind == "secret-assignment" and not scan_generic_assignments:
                continue
            match = pattern.search(line)
            if not match:
                continue
            if kind == "secret-assignment" and _is_placeholder(match.group(2)):
                continue
            issues.append(
                SecretScanIssue(
                    path=relative,
                    kind=kind,
                    line=line_number,
                    detail="possible secret material in tracked or unignored file",
                )
            )
    return issues


def scan_repository_for_secrets(repo_root: Path, allowlist_path: Path | None = None) -> list[SecretScanIssue]:
    root = repo_root.resolve()
    issues: list[SecretScanIssue] = []

    for path in _git_files(root):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        parts = set(relative_path.parts)
        suffix = path.suffix.lower()

        if relative_path.parts[:1] != ("templates",) and SENSITIVE_PATH_PARTS & parts:
            issues.append(
                SecretScanIssue(
                    path=relative,
                    kind="sensitive-path",
                    line=None,
                    detail="secrets must stay ignored and out of Git-visible files",
                )
            )
            continue

        if suffix in SENSITIVE_EXTENSIONS and ".example" not in path.name:
            issues.append(
                SecretScanIssue(
                    path=relative,
                    kind="sensitive-extension",
                    line=None,
                    detail=f"{suffix} files must stay in secrets/ or be committed only as examples",
                )
            )

        if path.stat().st_size <= 1_000_000:
            issues.extend(_scan_file_content(root, path))

    return _apply_allowlist(issues, load_secret_scan_allowlist(root, allowlist_path))
