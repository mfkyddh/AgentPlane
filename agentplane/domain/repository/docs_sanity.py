from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DOC_ROOTS = ("AGENTS.md", "README.md", "CONTRIBUTING.md", "docs")
SKIP_DOC_PARTS: set[str] = set()
ROOT_ENTRY_DOCS = {"AGENTS.md", "README.md"}
FRONTMATTER_REQUIRED_DIRS = {"reference", "maintainers", "runbooks", "getting-started", "architecture"}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
LAST_VERIFIED_RE = re.compile(r"^last_verified:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
CONCLUSION_RE = re.compile(r"结论[：:]", re.UNICODE)
AUDIENCE_RE = re.compile(r"^audience:\s*(human|agent|both)\s*$", re.MULTILINE)
README_MAX_LINES = 150  # 人类脸面文档必须极简
LAST_VERIFIED_MAX_AGE_DAYS = 30

# 人类面向文档中应避免的 AI 术语（中文+英文）
HUMAN_DOC_TERM_BLACKLIST = {
    "真源",
    "投影链",
    "投影",
    "台账投影",
    "台账",
    "Task-Entry",
    "task-entry",
    "Resolver",
    "resolver",
    "Ledger",
    "ledger",
    "Inventory",
    "inventory",
    "Contract",
    "contract",
    "Catalog",
    "catalog",
    "控制面",
    "Projection Chain",
    "projection chain",
    "Envelope",
    "envelope",
}

# 人类文档长度封顶（路径前缀 -> 最大行数）
HUMAN_DOC_LENGTH_LIMITS = [
    ("README.md", 150),
    ("docs/getting-started", 180),
    ("docs/tutorials", 250),
]

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
        if root.is_file() and root.suffix == ".md" and not _is_git_ignored(repo_root, root):
            docs.append(root)
        elif root.is_dir():
            for path in root.rglob("*.md"):
                relative_parts = set(path.relative_to(root).parts)
                if relative_parts & SKIP_DOC_PARTS:
                    continue
                if _is_git_ignored(repo_root, path):
                    continue
                docs.append(path)
    return sorted(docs)


def _is_git_ignored(repo_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", relative],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


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


def _is_archive_or_history(relative: str) -> bool:
    return "docs/archive/" in relative or "docs/history/" in relative


def _check_frontmatter(relative: str, text: str, doc_parts: set[str] | None) -> list[DocsSanityIssue]:
    """Check that docs under required dirs have frontmatter."""
    issues: list[DocsSanityIssue] = []
    if _is_archive_or_history(relative):
        return issues
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
                detail="docs must have YAML frontmatter with status/owner/last_verified/superseded_by/audience",
            )
        )
        return issues
    fm_text = match.group(1)
    for field in ("status", "owner", "last_verified", "superseded_by", "audience"):
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


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks and inline code spans from markdown text."""
    # Remove fenced code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", lambda m: "\n" * m.group(0).count("\n"), text)
    # Remove inline code (`...`)
    text = re.sub(r"`[^`]+`", " ", text)
    return text


def _check_audience_terminology(relative: str, text: str) -> list[DocsSanityIssue]:
    """Check that strictly human-facing docs avoid AI-only terminology.
    Docs marked 'both' are exempt because they need to reference formal commands and concepts.
    Code blocks are skipped because they contain formal CLI examples."""
    issues: list[DocsSanityIssue] = []
    audience_match = AUDIENCE_RE.search(text)
    if not audience_match:
        return issues
    audience = audience_match.group(1)
    if audience != "human":
        return issues
    prose = _strip_code_blocks(text)
    for term in HUMAN_DOC_TERM_BLACKLIST:
        for match in re.finditer(re.escape(term), prose):
            issues.append(
                DocsSanityIssue(
                    path=relative,
                    kind="ai-term-in-human-doc",
                    line=_line_for_offset(text, match.start()),
                    detail=f"术语 '{term}' 出现在人类面向文档中，请改用日常用语或将细节下钻到 reference/architecture 文档",
                    severity="warning",
                )
            )
    return issues


def _check_agents_redirect(relative: str, text: str) -> list[DocsSanityIssue]:
    """Check that AGENTS.md has a human redirect notice."""
    if relative != "AGENTS.md":
        return []
    if "getting-started" in text or "how-agent-works" in text or "人类读者" in text or "人类请" in text:
        return []
    return [
        DocsSanityIssue(
            path=relative,
            kind="missing-agents-human-redirect",
            line=1,
            detail="AGENTS.md must include a human redirect notice pointing to docs/getting-started/getting-started.md",
            severity="error",
        )
    ]


def _check_human_doc_length(relative: str, text: str) -> list[DocsSanityIssue]:
    """Check that human-facing docs do not exceed length limits."""
    issues: list[DocsSanityIssue] = []
    audience_match = AUDIENCE_RE.search(text)
    if not audience_match:
        # Also apply to README.md and docs without explicit audience if path matches
        pass
    else:
        audience = audience_match.group(1)
        if audience not in ("human", "both"):
            return issues

    line_count = len(text.splitlines())
    for prefix, max_lines in HUMAN_DOC_LENGTH_LIMITS:
        if relative == prefix or relative.startswith(prefix + "/"):
            if line_count > max_lines:
                issues.append(
                    DocsSanityIssue(
                        path=relative,
                        kind="human-doc-too-long",
                        line=None,
                        detail=f"human-facing doc has {line_count} lines (max {max_lines} for {prefix}); move detail to deeper docs",
                        severity="warning",
                    )
                )
            break
    return issues


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _check_image_references(relative: str, text: str, repo_root: Path) -> list[DocsSanityIssue]:
    """Check that local image references point to existing files."""
    issues: list[DocsSanityIssue] = []
    doc_path = repo_root / relative
    for match in IMAGE_RE.finditer(text):
        target = match.group(1)
        if not target or _is_external_link(target):
            continue
        target_path = (doc_path.parent / target).resolve()
        if not target_path.exists():
            issues.append(
                DocsSanityIssue(
                    path=relative,
                    kind="broken-image-reference",
                    line=_line_for_offset(text, match.start()),
                    detail=f"referenced image not found: {target}",
                )
            )
    return issues


def _check_archive_status(relative: str, text: str) -> list[DocsSanityIssue]:
    """Archive and history docs must not be marked as active."""
    issues: list[DocsSanityIssue] = []
    if "docs/archive/" not in relative and "docs/history/" not in relative:
        return issues
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        return issues
    if "status: active" in fm_match.group(1):
        issues.append(
            DocsSanityIssue(
                path=relative,
                kind="archive-doc-active",
                line=2,
                detail="archive/history docs must not have status: active; use status: archived or status: historical",
            )
        )
    return issues


def _check_conclusion_line(relative: str, text: str, doc_parts: set[str] | None) -> list[DocsSanityIssue]:
    """Check that docs under reference/maintainers/runbooks have a conclusion line."""
    issues: list[DocsSanityIssue] = []
    if _is_archive_or_history(relative):
        return issues
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

        # Broken local links (skip archive/history docs)
        if not _is_archive_or_history(relative):
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
                    target_relative = (
                        readme_path.relative_to(root).as_posix() if readme_path.exists() else target_relative
                    )
                if target_relative in inbound_links and target_relative != relative:
                    inbound_links[target_relative].add(relative)

        # Frontmatter checks
        issues.extend(_check_frontmatter(relative, text, doc_parts))

        # Conclusion line check
        issues.extend(_check_conclusion_line(relative, text, doc_parts))

        # Audience terminology check
        issues.extend(_check_audience_terminology(relative, text))

        # AGENTS.md human redirect check
        issues.extend(_check_agents_redirect(relative, text))

        # Human doc length check
        issues.extend(_check_human_doc_length(relative, text))

        # Image reference check
        issues.extend(_check_image_references(relative, text, root))

        # Archive/history status check
        issues.extend(_check_archive_status(relative, text))

    # Isolated active docs
    for relative, sources in sorted(inbound_links.items()):
        if relative in ROOT_ENTRY_DOCS:
            continue
        if "docs/archive/" in relative or "docs/history/" in relative:
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
