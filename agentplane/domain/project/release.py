"""Automated version bumping from conventional commits.

Reads the current version from pyproject.toml, analyses commits since the
last git tag, determines the semantic bump type, updates version + CHANGELOG,
and creates a release commit + tag.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from datetime import date
from pathlib import Path

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|refactor|perf|docs|test|chore|style)"
    r"(?:\([a-zA-Z0-9][a-zA-Z0-9._-]*\))?"
    r"(?P<breaking>!)?: "
    r"(?P<description>.+)$"
)

BUMP_ORDER = {"patch": 0, "minor": 1, "major": 2}
TYPE_TO_BUMP = {
    "feat": "minor",
    "fix": "patch",
    "refactor": "patch",
    "perf": "patch",
}


def get_current_version(repo_root: Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data["project"]["version"]


_RECORD_SEP = "<<<COMMIT>>>"


def _last_tag(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def get_commits_since_tag(repo_root: Path) -> list[dict[str, str]]:
    tag = _last_tag(repo_root)
    tag_ref = f"{tag}..HEAD" if tag else "HEAD"

    log = subprocess.run(
        ["git", "log", "--no-merges", f"--format=%H%n%s%n%b{_RECORD_SEP}", tag_ref],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if log.returncode != 0:
        return []

    commits: list[dict[str, str]] = []
    for record in log.stdout.split(_RECORD_SEP):
        record = record.strip()
        if not record:
            continue
        lines = record.splitlines()
        if len(lines) < 2:
            continue
        sha = lines[0].strip()
        subject = lines[1].strip()
        body = "\n".join(lines[2:])
        commits.append({"sha": sha, "subject": subject, "body": body})
    return commits


def determine_bump_type(commits: list[dict[str, str]], override: str | None = None) -> str:
    if override:
        if override not in BUMP_ORDER:
            raise ValueError(f"invalid bump type: {override}")
        return override

    highest = "patch"
    for commit in commits:
        subject = commit["subject"]
        body = commit["body"]
        match = CONVENTIONAL_RE.match(subject)
        if not match:
            continue
        commit_type = match.group("type")
        has_bang = match.group("breaking") is not None
        has_breaking_footer = "BREAKING CHANGE" in body

        if has_bang or has_breaking_footer:
            return "major"

        bump = TYPE_TO_BUMP.get(commit_type, "patch")
        if BUMP_ORDER[bump] > BUMP_ORDER[highest]:
            highest = bump

    return highest


def bump_version(current: str, bump_type: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"invalid bump type: {bump_type}")


def update_pyproject_version(repo_root: Path, new_version: str) -> None:
    path = repo_root / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(version\s*=\s*)"[^"]*"',
        f'\\1"{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def generate_changelog_entry(new_version: str, commits: list[dict[str, str]]) -> str:
    today = date.today().isoformat()
    lines = [f"## {new_version} — {today}", ""]
    for commit in commits:
        subject = commit["subject"]
        sha_short = commit["sha"][:7]
        lines.append(f"- {subject} ({sha_short})")
    lines.append("")
    return "\n".join(lines)


def update_changelog(repo_root: Path, entry: str) -> None:
    path = repo_root / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    marker = "# Changelog"
    idx = text.find(marker)
    if idx == -1:
        path.write_text(entry + text, encoding="utf-8")
        return
    insert_after = text.find("\n", idx)
    if insert_after == -1:
        insert_after = len(marker)
    else:
        insert_after += 1
    new_text = text[:insert_after] + "\n" + entry + text[insert_after:]
    path.write_text(new_text, encoding="utf-8")


def create_release_commit_and_tag(repo_root: Path, version: str) -> None:
    tag = f"v{version}"
    subprocess.run(
        ["git", "add", "pyproject.toml", "CHANGELOG.md"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"chore(release): {tag}"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "tag", tag],
        cwd=repo_root,
        check=True,
    )
