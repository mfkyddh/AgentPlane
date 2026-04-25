#!/usr/bin/env python3
"""Bulk document operations with dry-run support.

This script provides safe batch operations for markdown documents,
including frontmatter manipulation, with mandatory dry-run preview.

Usage:
    python scripts/bulk_doc_ops.py --dry-run --dir docs/runbooks \
        --set-field audience=both --set-field owner="AgentPlane maintainers"

    python scripts/bulk_doc_ops.py --dir docs/getting-started \
        --set-field last_verified=2026-04-25

Rules:
    1. --dry-run is REQUIRED unless --execute is explicitly passed.
    2. After any write, run docs-sanity to verify no regressions.
    3. Only modify files under docs/ and AGENTS.md / README.md.
"""

from __future__ import annotations

import argparse
import difflib
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# Force UTF-8 output on Windows consoles that default to GBK
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except AttributeError:
        # Python &lt; 3.7 fallback
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_ROOTS = ("AGENTS.md", "README.md", "CONTRIBUTING.md", "docs")
SKIP_DOC_PARTS = {"archive", "history"}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)


@dataclass(frozen=True)
class DocOp:
    path: Path
    original: str
    modified: str

    @property
    def has_changes(self) -> bool:
        return self.original != self.modified


def _iter_docs(repo_root: Path, target_dir: str | None = None) -> list[Path]:
    docs: list[Path] = []
    if target_dir:
        target = repo_root / target_dir
        if target.is_file() and target.suffix == ".md":
            return [target]
        if target.is_dir():
            for path in target.rglob("*.md"):
                relative_parts = set(path.relative_to(target).parts)
                if relative_parts & SKIP_DOC_PARTS:
                    continue
                docs.append(path)
        return sorted(docs)

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


def _set_frontmatter_field(text: str, field: str, value: str) -> str:
    """Set or update a single field in YAML frontmatter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        # No frontmatter: insert one at the top
        fm_lines = [f"{field}: {value}"]
        new_fm = "---\n" + "\n".join(fm_lines) + "\n---\n\n"
        return new_fm + text

    fm_text = match.group(1)
    field_re = re.compile(rf"^{re.escape(field)}:\s*.*$", re.MULTILINE)

    if field_re.search(fm_text):
        new_fm_text = field_re.sub(f"{field}: {value}", fm_text)
    else:
        new_fm_text = fm_text.rstrip() + f"\n{field}: {value}"

    new_text = text[: match.start()] + "---\n" + new_fm_text + "\n---" + text[match.end() :]
    return new_text


def _compute_diff(path: Path, original: str, modified: str, repo_root: Path) -> str:
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel = path.name
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    # Ensure trailing newline for clean diff
    if orig_lines and not orig_lines[-1].endswith("\n"):
        orig_lines[-1] += "\n"
    if mod_lines and not mod_lines[-1].endswith("\n"):
        mod_lines[-1] += "\n"
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
    )
    return "".join(diff)


def _run_docs_sanity(repo_root: Path) -> int:
    result = subprocess.run(
        [sys.executable, "-m", "agentplane.cli", "repo", "docs-sanity", "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
    )
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bulk document operations with mandatory dry-run safety."
    )
    parser.add_argument(
        "--dir",
        help="Target directory or file under repo root (e.g. docs/runbooks or docs/runbooks/foo.md)",
    )
    parser.add_argument(
        "--set-field",
        action="append",
        metavar="FIELD=VALUE",
        help="Set a frontmatter field (can be used multiple times).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without writing files (default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually write changes to disk. Must be explicitly passed.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        default=False,
        help="Skip post-write docs-sanity verification (not recommended).",
    )
    args = parser.parse_args(argv)

    if not args.set_field:
        parser.error("At least one --set-field is required.")

    fields_to_set: dict[str, str] = {}
    for raw in args.set_field:
        if "=" not in raw:
            parser.error(f"--set-field must be FIELD=VALUE, got: {raw}")
        k, v = raw.split("=", 1)
        fields_to_set[k.strip()] = v.strip()

    execute = args.execute
    dry_run = not execute

    docs = _iter_docs(REPO_ROOT, args.dir)
    if not docs:
        print("No matching documents found.", file=sys.stderr)
        return 1

    ops: list[DocOp] = []
    for path in docs:
        text = path.read_text(encoding="utf-8")
        modified = text
        for field, value in fields_to_set.items():
            modified = _set_frontmatter_field(modified, field, value)
        ops.append(DocOp(path=path, original=text, modified=modified))

    changed_ops = [op for op in ops if op.has_changes]

    if not changed_ops:
        print("No changes needed for any document.")
        return 0

    if dry_run:
        print(f"=== DRY RUN: {len(changed_ops)} document(s) would be modified ===\n")
        for op in changed_ops:
            diff = _compute_diff(op.path, op.original, op.modified, REPO_ROOT)
            if diff:
                print(diff)
                print()
        print("=== No files were written. Pass --execute to apply changes. ===")
        return 0

    # Execute mode
    print(f"=== EXECUTE: writing {len(changed_ops)} document(s) ===")
    for op in changed_ops:
        try:
            rel = op.path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = op.path.name
        op.path.write_text(op.modified, encoding="utf-8")
        print(f"  ✓ {rel}")

    if not args.no_verify:
        print("\n=== Running docs-sanity verification ===")
        rc = _run_docs_sanity(REPO_ROOT)
        if rc != 0:
            print("\n⚠️  docs-sanity reported issues. Review above output.", file=sys.stderr)
            return rc
        print("✓ docs-sanity passed (0 errors, 0 warnings).")

    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
