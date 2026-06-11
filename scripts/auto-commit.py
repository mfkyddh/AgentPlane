#!/usr/bin/env python3
"""Auto-commit script for AgentPlane.

Automatically commits changes after significant modifications.
Groups changes by type and generates conventional commit messages.

Usage:
    python scripts/auto-commit.py                    # Auto-detect and commit
    python scripts/auto-commit.py --dry-run          # Preview without committing
    python scripts/auto-commit.py --message "msg"    # Custom message
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def get_changed_files() -> list[str]:
    """Get list of changed files."""
    result = run_git("status", "--porcelain")
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def classify_changes(files: list[str]) -> dict[str, list[str]]:
    """Classify changes by type based on file paths."""
    categories: dict[str, list[str]] = {
        "tests": [],
        "docs": [],
        "config": [],
        "source": [],
        "scripts": [],
        "other": [],
    }
    
    for file in files:
        # Remove status prefix (M, A, D, ??, etc.)
        # Git status output format: "XY path" where XY is status
        path = file.strip()
        if len(path) > 2 and path[1] == ' ':
            path = path[2:]
        elif len(path) > 3 and path[2] == ' ':
            path = path[3:]
        
        if path.startswith("tests/") or path.startswith("tests\\"):
            categories["tests"].append(path)
        elif path.endswith(".md") or path.startswith("docs/") or path.startswith("docs\\"):
            categories["docs"].append(path)
        elif path in ("pyproject.toml", ".pre-commit-config.yaml", "AGENTS.md", "CLAUDE.md"):
            categories["config"].append(path)
        elif path.startswith("agentplane/") or path.startswith("agentplane\\"):
            categories["source"].append(path)
        elif path.startswith("scripts/") or path.startswith("scripts\\"):
            categories["scripts"].append(path)
        else:
            categories["other"].append(path)
    
    return categories


def generate_commit_message(categories: dict[str, list[str]], custom_message: str | None = None) -> str:
    """Generate a conventional commit message."""
    if custom_message:
        return custom_message
    
    # Determine primary type
    total = sum(len(files) for files in categories.values())
    
    if categories["source"]:
        if any("test" in f for f in categories["source"]):
            type_prefix = "test"
        elif any("fix" in f or "bug" in f for f in categories["source"]):
            type_prefix = "fix"
        else:
            type_prefix = "feat"
    elif categories["tests"]:
        type_prefix = "test"
    elif categories["docs"]:
        type_prefix = "docs"
    elif categories["scripts"]:
        type_prefix = "chore"
    elif categories["config"]:
        type_prefix = "chore"
    else:
        type_prefix = "chore"
    
    # Generate description
    parts = []
    if categories["source"]:
        parts.append(f"update {len(categories['source'])} source files")
    if categories["tests"]:
        parts.append(f"update {len(categories['tests'])} test files")
    if categories["docs"]:
        parts.append(f"update {len(categories['docs'])} docs")
    if categories["config"]:
        parts.append(f"update {len(categories['config'])} config files")
    if categories["scripts"]:
        parts.append(f"update {len(categories['scripts'])} scripts")
    
    description = ", ".join(parts) if parts else f"update {total} files"
    
    return f"{type_prefix}: {description}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-commit changes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without committing")
    parser.add_argument("--message", "-m", help="Custom commit message")
    parser.add_argument("--all", "-a", action="store_true", help="Stage all changes before committing")
    args = parser.parse_args()
    
    # Check if we're in a git repo
    result = run_git("rev-parse", "--git-dir")
    if result.returncode != 0:
        print("Error: Not in a git repository", file=sys.stderr)
        return 1
    
    # Get changed files
    files = get_changed_files()
    if not files:
        print("No changes to commit")
        return 0
    
    # Classify changes
    categories = classify_changes(files)
    
    # Generate commit message
    message = generate_commit_message(categories, args.message)
    
    # Preview
    print(f"Changes ({len(files)} files):")
    for category, cat_files in categories.items():
        if cat_files:
            print(f"  {category}: {len(cat_files)} files")
    print(f"\nCommit message: {message}")
    
    if args.dry_run:
        print("\n[dry-run] Would commit these changes")
        return 0
    
    # Stage all if requested
    if args.all:
        result = run_git("add", "-A")
        if result.returncode != 0:
            print(f"Error staging files: {result.stderr}", file=sys.stderr)
            return 1
    
    # Commit
    result = run_git("commit", "-m", message)
    if result.returncode != 0:
        print(f"Error committing: {result.stderr}", file=sys.stderr)
        return 1
    
    print(f"\nCommitted: {message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
