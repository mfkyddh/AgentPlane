"""Batch update test files for AgentPlane 4-domain refactoring."""
import pathlib

ROOT = pathlib.Path(r"d:\Projects\AgentPlane")

def replace_in_file(path: pathlib.Path, replacements: dict[str, str]) -> bool:
    content = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        path.write_text(content, encoding="utf-8")
        print(f"  Updated: {path}")
    return changed

# Common replacements for all test files
common = {
    "from agentplane.domain.infra.": "from agentplane.domain.infra.",
    "from agentplane.domain.ingress.": "from agentplane.domain.ingress.",
    "from agentplane.domain.app.projection.runtime_env": "from agentplane.domain.app.projection.runtime_env",
    "SUPPORTED_INFRA_TARGETS": "SUPPORTED_INFRA_TARGETS",
    "SUPPORTED_INGRESS_TARGETS": "SUPPORTED_INGRESS_TARGETS",
    "handle_infra_command": "handle_infra_command",
    "handle_ingress_command": "handle_ingress_command",
    "add_infra_parser": "add_infra_parser",
    "add_ingress_parser": "add_ingress_parser",
    "infra_action": "infra_action",
    "ingress_action": "ingress_action",
    "infra_live_gate_action": "infra_live_gate_action",
    'command="infra"': 'command="infra"',
    'command="ingress"': 'command="ingress"',
    "agentplane host ": "agentplane infra ",
    "agentplane website ": "agentplane ingress ",
    "test_host_": "test_infra_",
    "test_website_": "test_ingress_",
}

# Infra-specific replacements
infra_specific = {
    "host inventory": "infra inventory",
    "host audit": "infra audit",
    "host cleanup": "infra cleanup",
    "host automation": "infra automation",
    "host network": "infra network",
    "host remote": "infra remote",
    "host secrets": "infra secrets",
    "host local": "infra local",
    "host live-gate": "infra live-gate",
}

# Ingress-specific replacements
ingress_specific = {
    "IngressDefinition": "IngressDefinition",
    "IngressFollowThrough": "IngressFollowThrough",
    "website_object": "ingress_object",
    "website_publish": "ingress_publish",
    "available_ingresses": "available_ingresses",
    "search_ingresses": "search_ingresses",
    "verify_ingress": "verify_ingress",
    "plan_ingress_operation": "plan_ingress_operation",
    "apply_ingress_operation": "apply_ingress_operation",
    "refresh_ingress_ledger": "refresh_ingress_ledger",
    "build_ingress_follow_through": "build_ingress_follow_through",
    "summarize_website": "summarize_ingress",
}

# Process infra test files
print("=== Infra test files ===")
infra_dir = ROOT / "tests/infra"
if infra_dir.exists():
    for f in infra_dir.glob("*.py"):
        r = {**common, **infra_specific}
        replace_in_file(f, r)

# Process ingress test files
print("=== Ingress test files ===")
ingress_dir = ROOT / "tests/ingress"
if ingress_dir.exists():
    for f in ingress_dir.glob("*.py"):
        r = {**common, **ingress_specific}
        replace_in_file(f, r)

# Also rename test files
for f in infra_dir.glob("test_host_*.py"):
    new_name = f.name.replace("test_host_", "test_infra_")
    f.rename(f.parent / new_name)
    print(f"  Renamed: {f.name} -> {new_name}")

for f in ingress_dir.glob("test_website_*.py"):
    new_name = f.name.replace("test_website_", "test_ingress_")
    f.rename(f.parent / new_name)
    print(f"  Renamed: {f.name} -> {new_name}")

# Process onepanel test files
print("=== Onepanel test files ===")
onepanel_dir = ROOT / "tests/onepanel"
if onepanel_dir.exists():
    for f in onepanel_dir.glob("*.py"):
        replace_in_file(f, common)

# Process projection test files
print("=== Projection test files ===")
projection_dir = ROOT / "tests/projection"
if projection_dir.exists():
    for f in projection_dir.glob("*.py"):
        r = {**common}
        replace_in_file(f, r)

# Process repository-level test files
print("=== Repository test files ===")
repo_test_files = [
    ROOT / "tests/repository/test_cli_entrypoints.py",
    ROOT / "tests/repository/test_docs_no_legacy_terms.py",
    ROOT / "tests/repository/test_open_source_readiness.py",
]
for f in repo_test_files:
    if f.exists():
        replace_in_file(f, common)

print("\n=== Done ===")
