"""One-off script to split oversized test files. Run from repo root."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tests.support.paths import REPO_ROOT


def _is_test_class(name: str) -> bool:
    """Check if a class name looks like a test class."""
    return name.startswith("Test") or name.endswith("Tests") or name.endswith("Test")


def find_classes(content: str, *, test_only: bool = False) -> list[tuple[str, int, int]]:
    """Find all class definitions with their start and end lines.

    The start line includes any preceding decorators and comments.
    If test_only=True, only return classes that look like test classes
    (start with 'Test' or end with 'Tests'/'Test'), but use the actual
    boundaries from ALL classes so that support class content between
    test classes is not incorrectly absorbed.
    """
    lines = content.splitlines(keepends=True)
    class_re = re.compile(r"^class (\w+)")
    decorator_re = re.compile(r"^@")
    comment_re = re.compile(r"^(#|$)")

    # First pass: find ALL classes with their raw line numbers
    all_raw: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = class_re.match(line)
        if m:
            all_raw.append((m.group(1), i))

    # Calculate boundaries for ALL classes
    all_boundaries: list[tuple[str, int, int]] = []
    for idx, (name, class_line) in enumerate(all_raw):
        start = class_line
        while start > 0:
            prev = start - 1
            prev_line = lines[prev].strip()
            if decorator_re.match(prev_line) or comment_re.match(prev_line):
                start = prev
            else:
                break
        if idx + 1 < len(all_raw):
            _, next_class_line = all_raw[idx + 1]
            end = next_class_line
            while end > 0:
                prev = end - 1
                prev_line = lines[prev].strip()
                if decorator_re.match(prev_line) or comment_re.match(prev_line):
                    end = prev
                else:
                    break
            all_boundaries.append((name, start, end))
        else:
            all_boundaries.append((name, start, len(lines)))

    if not test_only:
        return all_boundaries

    # Filter to test classes only, preserving the original boundaries
    return [(n, s, e) for n, s, e in all_boundaries if _is_test_class(n)]


def find_helpers(content: str, first_class_line: int) -> list[tuple[str, int, int]]:
    """Find standalone helper functions before the first class."""
    lines = content.splitlines(keepends=True)
    helpers: list[tuple[str, int, int]] = []
    func_re = re.compile(r"^def (\w+)\(")
    current_func: str | None = None
    current_start = 0
    for i, line in enumerate(lines):
        if i >= first_class_line:
            break
        m = func_re.match(line)
        if m:
            if current_func:
                helpers.append((current_func, current_start, i))
            current_func = m.group(1)
            current_start = i
    if current_func:
        helpers.append((current_func, current_start, first_class_line))
    return helpers


def find_all_top_level_functions(content: str) -> list[tuple[str, int, int]]:
    """Find ALL top-level functions (not inside classes) in the entire file.

    A function's end is the line before the next top-level definition
    (function or class), or end of file.
    """
    lines = content.splitlines(keepends=True)
    funcs: list[tuple[str, int, int]] = []
    top_level_re = re.compile(r"^(def |class )")
    func_re = re.compile(r"^def (\w+)\(")
    current_func: str | None = None
    current_start = 0
    for i, line in enumerate(lines):
        if top_level_re.match(line):
            if current_func:
                funcs.append((current_func, current_start, i))
                current_func = None
            m = func_re.match(line)
            if m:
                current_func = m.group(1)
                current_start = i
    if current_func:
        funcs.append((current_func, current_start, len(lines)))
    return funcs


def find_standalone_test_functions(content: str, first_class_line: int) -> list[tuple[str, int, int]]:
    """Find standalone test functions (not in any class)."""
    lines = content.splitlines(keepends=True)
    funcs: list[tuple[str, int, int]] = []
    func_re = re.compile(r"^def (test_\w+)\(")
    current_func: str | None = None
    current_start = 0
    for i, line in enumerate(lines):
        if i >= first_class_line:
            break
        m = func_re.match(line)
        if m:
            if current_func:
                funcs.append((current_func, current_start, i))
            current_func = m.group(1)
            current_start = i
    if current_func:
        funcs.append((current_func, current_start, first_class_line))
    return funcs


def split_by_classes(
    source: Path,
    groups: list[tuple[str, list[str]]],
) -> dict[str, str]:
    """Split a multi-class file into multiple files by class grouping.

    Support classes (non-Test) that appear before a test class are
    automatically included with that test class's group. Each support
    class is assigned to exactly one group (the one containing the first
    test class that follows it).
    """
    content = source.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Find ALL classes (including support classes like FakeExecutor)
    all_classes = find_classes(content, test_only=False)
    # Find only test classes for the group definitions
    test_classes = find_classes(content, test_only=True)
    test_class_names = {n for n, _, _ in test_classes}

    # Assign support classes to the first test class that follows them.
    # Each support class goes to exactly one test class.
    support_before: dict[str, list[str]] = {}  # test_class -> [support_class_names]
    pending_support: list[str] = []
    for name, start, end in all_classes:
        if name in test_class_names:
            if pending_support:
                support_before[name] = pending_support
                pending_support = []
        else:
            pending_support.append(name)

    # Build a map from each test class to the effective start/end.
    # The effective start includes any assigned support classes.
    test_class_map: dict[str, tuple[int, int]] = {}
    all_class_map = {n: (s, e) for n, s, e in all_classes}
    for name, start, end in test_classes:
        effective_start = start
        for sname in support_before.get(name, []):
            if sname in all_class_map:
                effective_start = min(effective_start, all_class_map[sname][0])
        test_class_map[name] = (effective_start, end)

    # Find ALL top-level functions (before and after classes)
    all_funcs = find_all_top_level_functions(content)
    # Separate into helpers (non-test) and standalone test functions
    helper_texts = {n: (s, e) for n, s, e in all_funcs if not n.startswith("test_")}
    standalone_tests = {n: (s, e) for n, s, e in all_funcs if n.startswith("test_")}

    # Header: everything before the first helper function or first class.
    first_class_line = all_classes[0][1] if all_classes else len(lines)
    first_func_line = all_funcs[0][1] if all_funcs else len(lines)
    header_end = min(first_class_line, first_func_line)
    header = "".join(lines[:header_end])

    # Include ALL helper functions in every group's output.
    helper_block = "".join("".join(lines[s:e]) for _, (s, e) in sorted(helper_texts.items(), key=lambda x: x[1][0]))

    results: dict[str, str] = {}
    for gidx, (suffix, class_names) in enumerate(groups):
        class_blocks = []
        last_class_end = 0
        for cname in class_names:
            if cname not in test_class_map:
                print(f"  WARNING: class '{cname}' not found in {source.name}")
                continue
            s, e = test_class_map[cname]
            class_blocks.append("".join(lines[s:e]))
            last_class_end = max(last_class_end, e)

        # For the last group, append standalone test functions after the last class
        if gidx == len(groups) - 1 and standalone_tests:
            tail_blocks = []
            for fname, (fs, fe) in sorted(standalone_tests.items(), key=lambda x: x[1][0]):
                if fs >= last_class_end:
                    tail_blocks.append("".join(lines[fs:fe]))
            if tail_blocks:
                class_blocks.append("\n")
                class_blocks.extend(tail_blocks)

        new_content = header + helper_block + "\n".join(class_blocks)
        if not new_content.endswith("\n"):
            new_content += "\n"
        results[suffix] = new_content
    return results


def split_single_class(
    source: Path,
    class_name: str,
    method_groups: list[tuple[str, int, int]],
    *,
    include_helpers: bool = True,
) -> dict[str, str]:
    """Split a single-class file by grouping methods into new classes.

    method_groups: list of (suffix, start_method_index, end_method_index)
                   where indices are 0-based into the class's test methods.
    """
    content = source.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Find all classes
    all_classes = find_classes(content)
    class_map = {name: (s, e) for name, s, e in all_classes}

    if class_name not in class_map:
        print(f"  WARNING: class '{class_name}' not found")
        return {}

    class_start, class_end = class_map[class_name]

    # Find the class definition line (without decorators)
    class_def_re = re.compile(rf"^class {re.escape(class_name)}")
    class_def_line = class_start
    for i in range(class_start, class_end):
        if class_def_re.match(lines[i]):
            class_def_line = i
            break

    # Extract class header (decorators + class def + any class-level docstring/attributes)
    # Find first method to determine where header ends
    method_re = re.compile(r"^\s+def (test_\w+)\(")
    first_method_line = None
    for i in range(class_def_line, class_end):
        if method_re.match(lines[i]):
            first_method_line = i
            break

    if first_method_line is None:
        print(f"  WARNING: no test methods found in {class_name}")
        return {}

    class_header = "".join(lines[class_start:first_method_line])

    # Find all test methods with their boundaries
    methods: list[tuple[str, int, int]] = []
    for i in range(first_method_line, class_end):
        m = method_re.match(lines[i])
        if m:
            methods.append((m.group(1), i, i))

    # Calculate method end lines
    for idx in range(len(methods)):
        name, s, _ = methods[idx]
        if idx + 1 < len(methods):
            _, ns, _ = methods[idx + 1]
            methods[idx] = (name, s, ns)
        else:
            methods[idx] = (name, s, class_end)

    # Find ALL top-level functions
    all_funcs = find_all_top_level_functions(content)
    helper_texts = {n: "".join(lines[s:e]) for n, s, e in all_funcs if not n.startswith("test_")}

    header_end = all_funcs[0][1] if all_funcs else class_start
    header = "".join(lines[:header_end])

    # Build split files
    results: dict[str, str] = {}
    for suffix, start_idx, end_idx in method_groups:
        helper_block = "".join(helper_texts.values()) if include_helpers else ""
        method_blocks = []
        for mname, ms, me in methods[start_idx:end_idx]:
            method_blocks.append("".join(lines[ms:me]))

        new_content = header + helper_block + class_header + "".join(method_blocks)
        if not new_content.endswith("\n"):
            new_content += "\n"
        results[suffix] = new_content

    return results


def write_splits(
    source: Path,
    results: dict[str, str],
    *,
    dry_run: bool = False,
) -> None:
    """Write split results to files."""
    for suffix, content in results.items():
        target = source.parent / f"test_{suffix}.py"
        line_count = len(content.splitlines())
        print(f"  {target.name}: {line_count} lines")
        if not dry_run:
            target.write_text(content, encoding="utf-8")
    if not dry_run:
        print(f"  Original {source.name} should be deleted after verifying tests pass.")


def _count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("DRY RUN - no files will be written\n")

    tests = REPO_ROOT / "tests"

    # ==================================================================
    # Multi-class files (split by class grouping)
    # ==================================================================

    # --- test_service.py (916 → 4 files) ---
    # ServiceCliTests is 521 lines — split by method groups
    src = tests / "service" / "test_service.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        # Split ServiceCliTests methods
        write_splits(src, split_single_class(
            src, "ServiceCliTests",
            [
                ("service_cli_core", 0, 8),
                ("service_cli_extended", 8, 14),
            ],
        ), dry_run=dry)
        # Split remaining classes
        write_splits(src, split_by_classes(src, [
            ("service_apply", ["ServiceApplyCliTests", "ServiceLifecycleTests"]),
            ("service_endpoint", ["ServicePublicEndpointCliTests"]),
        ]), dry_run=dry)
        print()

    # --- test_onepanel_infra.py (834 → 3 files) ---
    src = tests / "onepanel" / "test_onepanel_infra.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("onepanel_infra_ingress", [
                "OnePanelPublicIngressTests",
                "ComposePolicyTests",
            ]),
            ("onepanel_infra_env", [
                "OnePanelEnvTargetsTests",
                "OnePanelFixtureManagerTests",
            ]),
            ("onepanel_infra_verify", [
                "OnePanelVerificationSuiteTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_nginxui_letsencrypt.py (796 → 2 files) ---
    src = tests / "infra" / "test_nginxui_letsencrypt.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("nginxui_cloudflare", [
                "TestLoadShellEnvFile",
                "TestParseBool",
                "TestCloudflareClientTokenAndZone",
                "TestCloudflareClientDnsRecord",
                "TestEnsureCloudflareDnsRecordScript",
                "TestCloudflareTokenValidation",
                "TestSkillDomainValidation",
            ]),
            ("nginxui_certbot", [
                "TestCertbotCommandConstruction",
                "TestCertificatePathVerification",
                "TestRenewalScriptContract",
                "TestDns01CertIssuanceScenario",
                "TestErrorScenarios",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_repo_structure.py (778 → 2 files) ---
    src = tests / "project" / "test_repo_structure.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("repo_structure_basics", [
                "RepositoryStructureTests",
                "OpenSourceReadinessTests",
                "SkillCatalogTests",
                "PyprojectConfigTests",
                "TestInfrastructureDriftPrevention",
            ]),
            ("repo_structure_governance", [
                "DocsNoLegacyTermsTests",
                "TruthPathPolicyTests",
                "CommitMessagePolicyTests",
                "CleanupTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_infra_automation.py (738 → 2 files) ---
    src = tests / "infra" / "test_infra_automation.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("infra_automation_checks", [
                "InfraAutomationTests",
                "TestCheckWslAvailable",
                "TestCheckSshConfigExists",
                "TestCheckSshKeyPermissions",
                "TestCheckSshReachable",
                "TestExecuteRemotePreflight",
            ]),
            ("infra_automation_ssh", [
                "SshTargetTests",
                "WslAuditTests",
                "WslFirstDocsTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_site_migration_ops.py (630 → 2 files) ---
    src = tests / "ingress" / "test_site_migration_ops.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("site_migration_reconcile", [
                "TestParallelValidation",
                "TestIngressReconcile",
                "TestDomainCutoverVerification",
            ]),
            ("site_migration_lifecycle", [
                "TestMigrationLifecycle",
                "TestFollowThrough",
                "TestEdgeCases",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_app_resource.py (570 → 2 files) ---
    src = tests / "app" / "test_app_resource.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("app_resource_cli", [
                "AppResourceCliTests",
                "AppResourceObjectCliTests",
            ]),
            ("app_resource_lifecycle", [
                "AppResourceLifecycleTests",
                "AppArtifactContractTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_ingress.py (543 → 2 files) ---
    src = tests / "ingress" / "test_ingress.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("ingress_website", [
                "WebsiteCliTests",
            ]),
            ("ingress_publish", [
                "WebsitePublishCliTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_onepanel_cli.py (520 → 2 files) ---
    src = tests / "onepanel" / "test_onepanel_cli.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("onepanel_cli_objects", [
                "OnePanelObjectApiTests",
                "OnePanelObjectCliHandlerTests",
            ]),
            ("onepanel_cli_plugins", [
                "OnePanelPluginAndSkillsTests",
                "OnePanelAppPlanTests",
            ]),
        ]), dry_run=dry)
        print()

    # --- test_runtime_core.py (597 → 2 files) ---
    src = tests / "runtime" / "test_runtime_core.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_by_classes(src, [
            ("runtime_core_runner", [
                "TestBackendRunnerExecuteStream",
                "TestClassifyError",
                "TestBackendRunnerErrorHandling",
            ]),
            ("runtime_core_execution", [
                "TestExecutionResultPayload",
            ]),
        ]), dry_run=dry)
        print()

    # ==================================================================
    # Single-class files (split by method groups)
    # ==================================================================

    # --- test_delivery_deploy.py (716 → 3 files) ---
    src = tests / "app" / "test_delivery_deploy.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "TestAppDeliveryDeployRollbackCliTests",
            [
                ("delivery_deploy_core", 0, 6),
                ("delivery_deploy_worktree", 6, 8),
                ("delivery_deploy_onepanel", 8, 17),
            ],
        ), dry_run=dry)
        print()

    # --- test_app_object_cli.py (673 → 3 files) ---
    src = tests / "app" / "test_app_object_cli.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "AppObjectCliTests",
            [
                ("app_object_search", 0, 4),
                ("app_object_get", 4, 13),
                ("app_object_verify_discover", 13, 20),
            ],
        ), dry_run=dry)
        print()

    # --- test_infra_host.py (528 → 2 files) ---
    src = tests / "infra" / "test_infra_host.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "HostCliTests",
            [
                ("infra_host_wrappers", 0, 10),
                ("infra_host_network", 10, 17),
            ],
        ), dry_run=dry)
        print()

    # --- test_repo_entrypoints.py (590 → 2 files) ---
    src = tests / "project" / "test_repo_entrypoints.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "CliEntrypointsTests",
            [
                ("repo_entrypoints_cli", 0, 5),
                ("repo_entrypoints_providers", 5, 17),
            ],
        ), dry_run=dry)
        print()

    # --- test_delivery_docsync.py (559 → 2 files) ---
    src = tests / "app" / "test_delivery_docsync.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "TestAppDeliveryDocSyncCliTests",
            [
                ("delivery_docsync_core", 0, 4),
                ("delivery_docsync_render", 4, 8),
            ],
        ), dry_run=dry)
        print()

    # --- test_onepanel_audit.py (511 → 2 files) ---
    src = tests / "onepanel" / "test_onepanel_audit.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "Prod0AuditTests",
            [
                ("onepanel_audit_policy", 0, 7),
                ("onepanel_audit_tenant", 7, 14),
            ],
        ), dry_run=dry)
        print()

    # --- test_delivery_verify.py (510 → 2 files) ---
    src = tests / "app" / "test_delivery_verify.py"
    if src.exists():
        print(f"Splitting {src.name} ({_count(src)} lines):")
        write_splits(src, split_single_class(
            src, "TestAppDeliveryRenderVerifyCliTests",
            [
                ("delivery_verify_render", 0, 5),
                ("delivery_verify_deploy", 5, 9),
            ],
        ), dry_run=dry)
        print()
