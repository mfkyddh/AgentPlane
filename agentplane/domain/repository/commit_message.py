"""Validate AgentPlane commit messages.

The module accepts either a commit message file path, as used by Git's
commit-msg hook, or a raw subject via --message.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_TYPES = ("feat", "fix", "refactor", "docs", "test", "chore", "style", "perf")
SUBJECT_RE = re.compile(
    r"^(?P<type>feat|fix|refactor|docs|test|chore|style|perf)"
    r"(?:\([a-z0-9][a-z0-9._-]*\))?: "
    r"(?P<description>[a-z0-9].*)$"
)


def _first_non_comment_line(message: str) -> str:
    for line in message.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def validate_subject(subject: str) -> list[str]:
    issues: list[str] = []

    if not subject:
        return ["commit message subject is empty"]

    match = SUBJECT_RE.match(subject)
    if not match:
        types = "|".join(ALLOWED_TYPES)
        issues.append(f"subject must match '<type>(<scope>): <description>' with type one of: {types}")
        return issues

    if len(subject) > 72:
        issues.append("subject must be 72 characters or fewer")

    if subject.endswith("."):
        issues.append("subject must not end with a period")

    return issues


def _subjects_from_range(commit_range: str) -> list[str]:
    range_spec = commit_range.strip()
    if not range_spec:
        return []

    # A bare SHA (no "..") means a single commit — only validate that one.
    if ".." not in range_spec:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", range_spec],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print(result.stderr.strip() or f"failed to inspect commit: {commit_range}", file=sys.stderr)
            raise SystemExit(2)
        subject = result.stdout.strip()
        return [subject] if subject else []

    base, head = range_spec.split("..", 1)
    if base and set(base) == {"0"}:
        range_spec = head

    result = subprocess.run(
        ["git", "log", "--no-merges", "--format=%s", range_spec],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or f"failed to inspect commit range: {commit_range}", file=sys.stderr)
        raise SystemExit(2)
    return [line for line in result.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an AgentPlane commit message.")
    parser.add_argument("message_file", nargs="?", help="Path to a Git commit message file.")
    parser.add_argument("--message", help="Raw commit message subject to validate.")
    parser.add_argument("--range", dest="commit_range", help="Git commit range to validate, excluding merge commits.")
    parser.add_argument("--range-env", help="Read the Git commit range from this environment variable.")
    args = parser.parse_args(argv)

    modes = [bool(args.message), bool(args.message_file), bool(args.commit_range), bool(args.range_env)]
    if sum(modes) != 1:
        parser.error("use exactly one of --message, --range, --range-env, or message_file")

    if args.message:
        subjects = [args.message.strip()]
    elif args.message_file:
        subjects = [_first_non_comment_line(Path(args.message_file).read_text(encoding="utf-8"))]
    elif args.range_env:
        subjects = _subjects_from_range(os.environ.get(args.range_env, ""))
    else:
        subjects = _subjects_from_range(args.commit_range)

    invalid: list[tuple[str, list[str]]] = []
    for subject in subjects:
        issues = validate_subject(subject)
        if issues:
            invalid.append((subject, issues))

    if invalid:
        for subject, issues in invalid:
            print("Invalid commit message:")
            print(f"  {subject}")
            for issue in issues:
                print(f"- {issue}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
