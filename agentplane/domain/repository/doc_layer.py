"""Validate that docs reside in the correct layer directory and carry a layer frontmatter field.

Four-layer documentation system:
  strategy   -> docs/strategy/
  project    -> docs/project/
  engineering -> docs/reference/
  technical  -> docs/architecture/, docs/runbooks/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
LAYER_RE = re.compile(r"^layer:\s*(\S+)", re.MULTILINE)

# directory prefix (relative to docs/) -> expected layer value
DIR_LAYER_MAP: dict[str, str] = {
    "strategy/": "strategy",
    "project/": "project",
    "reference/": "engineering",
    "architecture/": "technical",
    "runbooks/": "technical",
}

# directories that are exempt from layer checks (not part of the four-layer system)
EXEMPT_PREFIXES: tuple[str, ...] = (
    "archive/",
    "history/",
    "getting-started/",
    "tutorials/",
    "maintainers/",
    "schemas/",
)

VALID_LAYERS = {"strategy", "project", "engineering", "technical"}


@dataclass(frozen=True)
class DocLayerIssue:
    path: str
    kind: str
    detail: str
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "detail": self.detail,
            "severity": self.severity,
        }


def _expected_layer(docs_relative: str) -> str | None:
    """Return the expected layer for a path relative to docs/, or None if exempt."""
    for prefix in EXEMPT_PREFIXES:
        if docs_relative.startswith(prefix):
            return None
    for prefix, layer in DIR_LAYER_MAP.items():
        if docs_relative.startswith(prefix):
            return layer
    # docs/ root files (like README.md) are exempt
    return None


def _extract_layer(text: str) -> str | None:
    """Extract the layer value from YAML frontmatter, if present."""
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    layer_match = LAYER_RE.search(fm_match.group(1))
    return layer_match.group(1) if layer_match else None


def run_doc_layer_check(repo_root: Path) -> list[DocLayerIssue]:
    """Check every .md file under docs/ for correct layer placement and annotation."""
    root = repo_root.resolve()
    docs_dir = root / "docs"
    if not docs_dir.is_dir():
        return []

    issues: list[DocLayerIssue] = []

    for md_path in sorted(docs_dir.rglob("*.md")):
        docs_relative = md_path.relative_to(docs_dir).as_posix()
        expected = _expected_layer(docs_relative)
        if expected is None:
            continue  # exempt directory

        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue

        actual = _extract_layer(text)
        rel_from_root = md_path.relative_to(root).as_posix()

        if actual is None:
            issues.append(
                DocLayerIssue(
                    path=rel_from_root,
                    kind="missing-layer-field",
                    detail=f"frontmatter 缺少 layer 字段；该文件位于 {expected} 层目录，应添加 layer: {expected}",
                )
            )
        elif actual not in VALID_LAYERS:
            issues.append(
                DocLayerIssue(
                    path=rel_from_root,
                    kind="invalid-layer-value",
                    detail=f"layer 值 '{actual}' 不合法，有效值: {', '.join(sorted(VALID_LAYERS))}",
                )
            )
        elif actual != expected:
            issues.append(
                DocLayerIssue(
                    path=rel_from_root,
                    kind="layer-mismatch",
                    detail=f"文件位于 {expected} 层目录，但 frontmatter 标注为 layer: {actual}",
                    severity="warning",
                )
            )

    return issues
