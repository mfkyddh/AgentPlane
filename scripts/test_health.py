"""Test suite health check script.

Run monthly or before major releases to detect test rot early.

Usage:
    python scripts/test_health.py [--json]

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# Thresholds from tests/STYLE_GUIDE.md
FILE_SIZE_WARN = 400
FILE_SIZE_FAIL = 500
CLASS_SIZE_WARN = 20
CLASS_SIZE_FAIL = 30
CONCONFTEST_SIZE_WARN = 80
CONCONFTEST_FAIL = 100
SUPPORT_SIZE_WARN = 300
SUPPORT_SIZE_FAIL = 400

# Patterns to detect
HARDCODED_IP_RE = re.compile(r'["\']127\.0\.0\.1:\d+["\']')
HARDCODED_DOMAIN_RE = re.compile(r'["\'][a-z0-9-]+\.(example|test|local)\.(com|net|org|io)["\']')
UNITTEST_CLASS_RE = re.compile(r"class \w+\(unittest\.TestCase\):")
PYTEST_CLASS_RE = re.compile(r"class Test\w+(?!\(unittest\.TestCase\)):")
CLASS_DEF_RE = re.compile(r"^class (Test\w+)", re.MULTILINE)
METHOD_DEF_RE = re.compile(r"^\s+def (test_\w+)", re.MULTILINE)


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _is_heredoc_line(line: str, in_heredoc: bool) -> tuple[bool, bool]:
    """Track heredoc state. Returns (in_heredoc, is_heredoc_boundary)."""
    stripped = line.strip()
    if in_heredoc:
        if stripped in ("'''", '"""', "```"):
            return False, True
        return True, False
    if any(stripped.startswith(p) for p in ('"""', "'''", "```")):
        if stripped.count(stripped[:3]) >= 2 and len(stripped) > 6:
            return False, False  # single-line string
        return True, True
    return False, False


class HealthReport:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.passed = True

    def add(self, name: str, status: str, details: list[str]) -> None:
        self.checks.append({"name": name, "status": status, "details": details})
        if status == "FAIL":
            self.passed = False

    def to_dict(self) -> dict:
        return {"ok": self.passed, "checks": self.checks}


def check_file_sizes(report: HealthReport) -> None:
    """Check test file line counts against thresholds."""
    issues: list[str] = []
    for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
        lines = _count_lines(py_file)
        rel = py_file.relative_to(REPO_ROOT)
        if lines > FILE_SIZE_FAIL:
            issues.append(f"FAIL {rel}: {lines} lines (max {FILE_SIZE_FAIL})")
        elif lines > FILE_SIZE_WARN:
            issues.append(f"WARN {rel}: {lines} lines (warn {FILE_SIZE_WARN})")

    status = "FAIL" if any("FAIL" in i for i in issues) else ("WARN" if issues else "PASS")
    report.add("file-sizes", status, issues or ["All test files within limits"])


def check_class_sizes(report: HealthReport) -> None:
    """Check test class method counts."""
    issues: list[str] = []
    for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(REPO_ROOT)

        for class_match in CLASS_DEF_RE.finditer(content):
            class_name = class_match.group(1)
            class_start = class_match.start()
            # Find next class or end of file
            next_class = CLASS_DEF_RE.search(content, class_start + 1)
            class_end = next_class.start() if next_class else len(content)
            class_body = content[class_start:class_end]
            method_count = len(METHOD_DEF_RE.findall(class_body))

            if method_count > CLASS_SIZE_FAIL:
                issues.append(f"FAIL {rel}::{class_name}: {method_count} methods (max {CLASS_SIZE_FAIL})")
            elif method_count > CLASS_SIZE_WARN:
                issues.append(f"WARN {rel}::{class_name}: {method_count} methods (warn {CLASS_SIZE_WARN})")

    status = "FAIL" if any("FAIL" in i for i in issues) else ("WARN" if issues else "PASS")
    report.add("class-sizes", status, issues or ["All test classes within limits"])


def check_style_mix(report: HealthReport) -> None:
    """Check ratio of unittest.TestCase vs pytest-native classes."""
    unittest_count = 0
    pytest_count = 0

    for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
        content = py_file.read_text(encoding="utf-8")
        unittest_count += len(UNITTEST_CLASS_RE.findall(content))
        pytest_count += len(PYTEST_CLASS_RE.findall(content))

    total = unittest_count + pytest_count
    if total == 0:
        report.add("style-ratio", "PASS", ["No test classes found"])
        return

    unittest_pct = (unittest_count / total) * 100
    issues: list[str] = []
    if unittest_pct > 50:
        issues.append(f"WARN unittest.TestCase: {unittest_count}/{total} ({unittest_pct:.0f}%)")
        issues.append("New tests should use pytest-native style")
        status = "WARN"
    else:
        issues.append(f"unittest.TestCase: {unittest_count}/{total} ({unittest_pct:.0f}%)")
        issues.append(f"pytest-native: {pytest_count}/{total} ({100 - unittest_pct:.0f}%)")
        status = "PASS"

    report.add("style-ratio", status, issues)


def check_hardcoded_fixtures(report: HealthReport) -> None:
    """Check for hardcoded IPs and domains outside constants.py and heredocs."""
    issues: list[str] = []

    for py_file in sorted(TESTS_DIR.rglob("*.py")):
        # Skip constants.py itself
        if py_file.name == "constants.py":
            continue

        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(REPO_ROOT)
        lines = content.splitlines()

        in_heredoc = False
        ip_hits = 0
        domain_hits = 0

        for line in lines:
            in_heredoc, _ = _is_heredoc_line(line, in_heredoc)
            if in_heredoc:
                continue
            ip_hits += len(HARDCODED_IP_RE.findall(line))
            domain_hits += len(HARDCODED_DOMAIN_RE.findall(line))

        if ip_hits > 0:
            issues.append(f"{rel}: {ip_hits} hardcoded IP references")
        if domain_hits > 0:
            issues.append(f"{rel}: {domain_hits} hardcoded domain references")

    status = "FAIL" if len(issues) > 3 else ("WARN" if issues else "PASS")
    if issues:
        issues.insert(0, f"Found {len(issues)} files with hardcoded fixture values")
        issues.append("Move fixture inputs to tests/support/constants.py")
    else:
        issues.append("No hardcoded fixture values detected")

    report.add("hardcoded-fixtures", status, issues)


def check_support_file_sizes(report: HealthReport) -> None:
    """Check support module line counts."""
    issues: list[str] = []
    support_dir = TESTS_DIR / "support"
    if not support_dir.exists():
        report.add("support-sizes", "PASS", ["No support directory"])
        return

    for py_file in sorted(support_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        lines = _count_lines(py_file)
        rel = py_file.relative_to(REPO_ROOT)
        if lines > SUPPORT_SIZE_FAIL:
            issues.append(f"FAIL {rel}: {lines} lines (max {SUPPORT_SIZE_FAIL})")
        elif lines > SUPPORT_SIZE_WARN:
            issues.append(f"WARN {rel}: {lines} lines (warn {SUPPORT_SIZE_WARN})")

    status = "FAIL" if any("FAIL" in i for i in issues) else ("WARN" if issues else "PASS")
    report.add("support-sizes", status, issues or ["All support modules within limits"])


def check_conftest_sizes(report: HealthReport) -> None:
    """Check conftest.py line counts."""
    issues: list[str] = []
    for conftest in sorted(TESTS_DIR.rglob("conftest.py")):
        lines = _count_lines(conftest)
        rel = conftest.relative_to(REPO_ROOT)
        if lines > CONCONFTEST_FAIL:
            issues.append(f"FAIL {rel}: {lines} lines (max {CONCONFTEST_FAIL})")
        elif lines > CONCONFTEST_SIZE_WARN:
            issues.append(f"WARN {rel}: {lines} lines (warn {CONCONFTEST_SIZE_WARN})")

    status = "FAIL" if any("FAIL" in i for i in issues) else ("WARN" if issues else "PASS")
    report.add("conftest-sizes", status, issues or ["All conftest files within limits"])


def check_duplicate_helpers(report: HealthReport) -> None:
    """Check for duplicate helper function definitions across test files."""
    func_locations: dict[str, list[str]] = {}

    for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
        content = py_file.read_text(encoding="utf-8")
        rel = str(py_file.relative_to(REPO_ROOT))
        # Find top-level function definitions (not methods)
        for match in re.finditer(r"^def (\w+)\(", content, re.MULTILINE):
            func_name = match.group(1)
            if func_name.startswith("_"):
                continue  # Skip private helpers
            func_locations.setdefault(func_name, []).append(rel)

    duplicates = {k: v for k, v in func_locations.items() if len(v) > 1}
    issues: list[str] = []
    for func_name, files in sorted(duplicates.items()):
        issues.append(f"'{func_name}' defined in: {', '.join(files)}")

    status = "WARN" if issues else "PASS"
    if issues:
        issues.insert(0, f"Found {len(duplicates)} duplicate helper functions")
        issues.append("Move shared helpers to tests/support/")
    else:
        issues.append("No duplicate helper functions detected")

    report.add("duplicate-helpers", status, issues)


def main() -> int:
    use_json = "--json" in sys.argv

    report = HealthReport()
    check_file_sizes(report)
    check_class_sizes(report)
    check_style_mix(report)
    check_hardcoded_fixtures(report)
    check_support_file_sizes(report)
    check_conftest_sizes(report)
    check_duplicate_helpers(report)

    if use_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("Test Suite Health Report")
        print("=" * 60)
        for check in report.checks:
            icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[check["status"]]
            print(f"\n[{icon}] {check['name']}")
            for detail in check["details"]:
                print(f"    {detail}")

        print("\n" + "=" * 60)
        overall = "ALL CHECKS PASSED" if report.passed else "SOME CHECKS FAILED"
        print(f"Result: {overall}")
        print("=" * 60)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
