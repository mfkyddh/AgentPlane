from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

DOC_ROOTS = ("AGENTS.md", "README.md", "CONTRIBUTING.md", "docs")
SKIP_DOC_PARTS = {"archive", "history"}
ROOT_ENTRY_DOCS = {"AGENTS.md", "README.md"}
FRONTMATTER_REQUIRED_DIRS = {"reference", "maintainers", "runbooks"}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
LAST_VERIFIED_RE = re.compile(r"^last_verified:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
CONCLUSION_RE = re.compile(r"结论[：:]", re.UNICODE)
README_MAX_LINES = 200
LAST_VERIFIED_MAX_AGE_DAYS = 30

RETIRED_ENTRYPOINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("retired-host-entrypoint", re.compile(r"\bagentplane(?:\.cli)?\s+host\b")),
    ("retired-website-entrypoint", re.compile(r"\bagentplane(?:\.cli)?\s+website\b")),
    ("retired-top-level-automation", re.compile(r"\bagentplane(?:\.cli)?\s+automation\b")),
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class DocsSanityIssue:
    path: str
    kind: str
    line: int | None
    detail: str
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "line": self.line,
            "detail": self.detail,
            "severity": self.severity,
        }


def _iter_docs(repo_root: Path) -> list[Path]:
    docs: list[Path] = []
    for root_name in DOC_ROOTS:
        root = repo_root / root_name
        if root.is_file() and root.suffix == ".md":
            docs.append(root)
        elif root.is_dir():
            for path in root.rglob("*.md"):
                relative_parts = set(path.relative_to(root).parts)
                if relative_parts & SKIP_DOC_PARTS:
                    continue
                docs.append(path)
    return sorted(docs)


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_external_link(target: str) -> bool:
    return "://" in target or target.startswith("#") or target.startswith("mailto:")


def _local_link_path(target: str) -> str:
    return target.split("#", 1)[0].strip()


def _relative_parts_under_docs(path: Path, root: Path) -> set[str] | None:
    """Return the set of path parts between docs/ and the file, or None if not under docs/."""
    try:
        rel = path.relative_to(root / "docs")
    except ValueError:
        return None
    parts = set(rel.parts)
    parts.discard(path.name)
    return parts


def _check_frontmatter(relative: str, text: str, doc_parts: set[str] | None) -> list[DocsSanityIssue]:
    """Check that docs under reference/maintainers/runbooks have frontmatter."""
    issues: list[DocsSanityIssue] = []
    if doc_parts is None:
        return issues
    if not (doc_parts & FRONTMATTER_REQUIRED_DIRS):
        return issues
    match = FRONTMATTER_RE.match(text)
    if not match:
        issues.append(
            DocsSanityIssue(
                path=relative,
                kind="missing-frontmatter",
                line=1,
                detail="docs under reference/maintainers/runbooks must have YAML frontmatter with status/owner/last_verified/superseded_by",
            )
        )
    else:
        fm_text = match.group(1)
        for field in ("status", "owner", "last_verified", "superseded_by"):
            if field not in fm_text:
                issues.append(
                    DocsSanityIssue(
                        path=relative,
                        kind="incomplete-frontmatter",
                        line=2,
                        detail=f"frontmatter missing required field: {field}",
                    )
                )
        # Check last_verified freshness
        lv_match = LAST_VERIFIED_RE.search(fm_text)
        if lv_match:
            try:
                lv_date = date.fromisoformat(lv_match.group(1))
                age = (date.today() - lv_date).days
                if age > LAST_VERIFIED_MAX_AGE_DAYS:
                    issues.append(
                        DocsSanityIssue(
                            path=relative,
                            kind="stale-last-verified",
                            line=None,
                            detail=f"last_verified is {age} days old (max {LAST_VERIFIED_MAX_AGE_DAYS}); please review and update",
                            severity="warning",
                        )
                    )
            except ValueError:
                pass
    return issues


def _check_readme_length(repo_root: Path) -> list[DocsSanityIssue]:
    """Warn if README.md exceeds the recommended line count."""
    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        return []
    line_count = len(readme_path.read_text(encoding="utf-8").splitlines())
    if line_count > README_MAX_LINES:
        return [
            DocsSanityIssue(
                path="README.md",
                kind="readme-too-long",
                line=None,
                detail=f"README.md has {line_count} lines (recommended max {README_MAX_LINES}); consider moving detail to docs/",
                severity="warning",
            )
        ]
    return []


def _check_conclusion_line(relative: str, text: str, doc_parts: set[str] | None) -> list[DocsSanityIssue]:
    """Check that docs under reference/maintainers/runbooks have a conclusion line."""
    issues: list[DocsSanityIssue] = []
    if doc_parts is None:
        return issues
    if not (doc_parts & FRONTMATTER_REQUIRED_DIRS):
        return issues
    # Skip docs/README.md (document map, doesn't need conclusion)
    if relative == "docs/README.md":
        return issues
    if CONCLUSION_RE.search(text):
        return issues
    issues.append(
        DocsSanityIssue(
            path=relative,
            kind="missing-conclusion",
            line=None,
            detail="active docs under reference/maintainers/runbooks should start with a conclusion line (结论：...)",
            severity="warning",
        )
    )
    return issues


def run_docs_sanity(repo_root: Path) -> list[DocsSanityIssue]:
    root = repo_root.resolve()
    issues: list[DocsSanityIssue] = []
    docs = _iter_docs(root)
    active_doc_relpaths = {path.relative_to(root).as_posix() for path in docs}
    inbound_links: dict[str, set[str]] = {relative: set() for relative in active_doc_relpaths}

    # README length check
    issues.extend(_check_readme_length(root))

    for path in docs:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        doc_parts = _relative_parts_under_docs(path, root)

        # Retired entrypoints
        for kind, pattern in RETIRED_ENTRYPOINTS:
            for match in pattern.finditer(text):
                issues.append(
                    DocsSanityIssue(
                        path=relative,
                        kind=kind,
                        line=_line_for_offset(text, match.start()),
                        detail="active docs must use current formal entrypoints",
                    )
                )

        # Broken local links
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = _local_link_path(match.group(1))
            if not target or _is_external_link(target):
                continue
            target_path = (path.parent / target).resolve()
            try:
                target_relative = target_path.relative_to(root).as_posix()
            except ValueError:
                continue
            if not target_path.exists():
                issues.append(
                    DocsSanityIssue(
                        path=relative,
                        kind="broken-local-link",
                        line=_line_for_offset(text, match.start()),
                        detail=f"missing local markdown target: {target}",
                    )
                )
                continue
            if target_path.is_dir():
                readme_path = target_path / "README.md"
                target_relative = readme_path.relative_to(root).as_posix() if readme_path.exists() else target_relative
            if target_relative in inbound_links and target_relative != relative:
                inbound_links[target_relative].add(relative)

        # Frontmatter checks
        issues.extend(_check_frontmatter(relative, text, doc_parts))

        # Conclusion line check
        issues.extend(_check_conclusion_line(relative, text, doc_parts))

    # Isolated active docs
    for relative, sources in sorted(inbound_links.items()):
        if relative in ROOT_ENTRY_DOCS:
            continue
        if not sources:
            issues.append(
                DocsSanityIssue(
                    path=relative,
                    kind="isolated-active-doc",
                    line=None,
                    detail="active docs must be discoverable from another active markdown document",
                )
            )

    return issues
