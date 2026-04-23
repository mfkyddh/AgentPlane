"""Batch rename script for AgentPlane 4-domain refactoring."""
import pathlib

ROOT = pathlib.Path(r"d:\Projects\AgentPlane")

def replace_in_file(path: pathlib.Path, replacements: dict[str, str]) -> None:
    content = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        path.write_text(content, encoding="utf-8")
        print(f"  Updated: {path}")

# 1. ingress/lifecycle.py
print("=== ingress/lifecycle.py ===")
r = {
    "build_ingress_follow_through": "build_ingress_follow_through",
    "resolve_ingress_verification_profile": "resolve_ingress_verification_profile",
    "IngressFollowThrough": "IngressFollowThrough",
    "IngressDefinition": "IngressDefinition",
    "SUPPORTED_INGRESS_TARGETS": "SUPPORTED_INGRESS_TARGETS",
    "plan_website_truth_onboard": "plan_ingress_truth_onboard",
    "apply_website_truth_onboard": "apply_ingress_truth_onboard",
    "plan_website_truth_offboard": "plan_ingress_truth_offboard",
    "apply_website_truth_offboard": "apply_ingress_truth_offboard",
    "_append_website": "_append_ingress",
    "_replace_website": "_replace_ingress",
    "_remove_website": "_remove_ingress",
    "summarize_website": "summarize_ingress",
    "unsupported website target": "unsupported ingress target",
    "website.truth.onboard": "ingress.truth.onboard",
    "website.truth.offboard": "ingress.truth.offboard",
    'unable to replace website': "unable to replace ingress",
    "unable to remove website": "unable to remove ingress",
    "website publish/reconcile": "ingress publish/reconcile",
}
p = ROOT / "agentplane/domain/ingress/lifecycle.py"
c = p.read_text(encoding="utf-8")
for old, new in r.items():
    c = c.replace(old, new)
# Fix remaining string references
c = c.replace('"source_surface": "ingress"', '"source_surface": "ingress"')
c = c.replace('"owner_surface": "projection"', '"owner_surface": "infra"')
p.write_text(c, encoding="utf-8")
print(f"  Updated: {p}")

# 2. domain/app/lifecycle.py
print("=== app/lifecycle.py ===")
p2 = ROOT / "agentplane/domain/app/lifecycle.py"
c2 = p2.read_text(encoding="utf-8")
c2 = c2.replace("from agentplane.domain.ingress.lifecycle import", "from agentplane.domain.ingress.lifecycle import")
c2 = c2.replace("from agentplane.domain.ingress.models import IngressDefinition", "from agentplane.domain.ingress.models import IngressDefinition")
c2 = c2.replace("from agentplane.domain.app.projection.runtime_env import", "from agentplane.domain.app.projection.runtime_env import")
c2 = c2.replace("apply_website_truth_onboard", "apply_ingress_truth_onboard")
c2 = c2.replace("apply_website_truth_offboard", "apply_ingress_truth_offboard")
c2 = c2.replace("plan_website_truth_onboard", "plan_ingress_truth_onboard")
c2 = c2.replace("plan_website_truth_offboard", "plan_ingress_truth_offboard")
c2 = c2.replace("IngressDefinition", "IngressDefinition")
c2 = c2.replace("_website_definitions", "_ingress_definitions")
c2 = c2.replace("_website_sites", "_ingress_sites")
p2.write_text(c2, encoding="utf-8")
print(f"  Updated: {p2}")

# 3. cli/projection.py
print("=== cli/projection.py ===")
p3 = ROOT / "agentplane/cli/projection.py"
c3 = p3.read_text(encoding="utf-8")
c3 = c3.replace("from agentplane.domain.app.projection.runtime_env import", "from agentplane.domain.app.projection.runtime_env import")
p3.write_text(c3, encoding="utf-8")
print(f"  Updated: {p3}")

# 4. domain/infra/__init__.py (ensure it exists)
print("=== domain/infra/__init__.py ===")
init_file = ROOT / "agentplane/domain/infra/__init__.py"
if not init_file.exists():
    init_file.write_text("", encoding="utf-8")
    print(f"  Created: {init_file}")

# 5. domain/app/projection/__init__.py
print("=== domain/app/projection/__init__.py ===")
proj_init = ROOT / "agentplane/domain/app/projection/__init__.py"
if not proj_init.exists():
    proj_init.write_text("", encoding="utf-8")
    print(f"  Created: {proj_init}")

print("\n=== Done ===")
