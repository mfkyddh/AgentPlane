from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DOC_ROOTS = ("AGENTS.md", "README.md", "CONTRIBUTING.md", "docs")
SKIP_DOC_PARTS = {"archive", "history"}
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

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "line": self.line,
            "detail": self.detail,
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


def run_docs_sanity(repo_root: Path) -> list[DocsSanityIssue]:
    root = repo_root.resolve()
    issues: list[DocsSanityIssue] = []

    for path in _iter_docs(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")

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

        for match in MARKDOWN_LINK_RE.finditer(text):
            target = _local_link_path(match.group(1))
            if not target or _is_external_link(target):
                continue
            target_path = (path.parent / target).resolve()
            try:
                target_path.relative_to(root)
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

    return issues
