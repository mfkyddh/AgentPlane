"""Batch update inventory, plugins, and remaining files."""
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
        print(f"  Updated: {path.relative_to(ROOT)}")
    return changed

r = {
    "agentplane host ": "agentplane infra ",
    "agentplane website ": "agentplane ingress ",
    "agentplane projection verification": "agentplane projection verification",  # keep
    "agentplane projection ledger": "agentplane projection ledger",  # keep
    "agentplane projection fixture": "agentplane projection fixture",  # keep
    "agentplane projection runtime-env": "agentplane projection runtime-env",  # keep
    "agentplane onepanel": "agentplane onepanel",  # keep
    "`host`": "`infra`",
    "`website`": "`ingress`",
    "host inventory": "infra inventory",
    "host audit": "infra audit",
    "host cleanup": "infra cleanup",
    "host automation": "infra automation",
    "host network": "infra network",
    "host remote": "infra remote",
    "host secrets": "infra secrets",
    "host live-gate": "infra live-gate",
    "website search": "ingress search",
    "website get": "ingress get",
    "website verify": "ingress verify",
    "website plan": "ingress plan",
    "website apply": "ingress apply",
    "website publish": "ingress publish",
    "website refresh-ledger": "ingress refresh-ledger",
    "主机级": "基础设施级",
    "主机基线": "基础设施基线",
    "主机自动化": "基础设施自动化",
}

# Inventory JSON files (keep public_ingresses key as it's data format)
inv_json_files = list((ROOT / "inventory").glob("**/*.json"))
print(f"=== Inventory JSON files ({len(inv_json_files)}) ===")
for f in inv_json_files:
    if f.is_file():
        replace_in_file(f, r)

# Inventory MD files
inv_md_files = list((ROOT / "inventory").glob("**/*.md"))
print(f"=== Inventory MD files ({len(inv_md_files)}) ===")
for f in inv_md_files:
    if f.is_file():
        replace_in_file(f, r)

# Plugin files
plugin_files = list((ROOT / "plugins").glob("**/*"))
print(f"=== Plugin files ({len([f for f in plugin_files if f.is_file()])}) ===")
for f in plugin_files:
    if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml"):
        replace_in_file(f, r)

# Rename plugin skill directories
skills_dir = ROOT / "plugins/agentplane-control-plane/skills"
if skills_dir.exists():
    host_skill = skills_dir / "hosts"
    infra_skill = skills_dir / "infra"
    if host_skill.exists() and not infra_skill.exists():
        host_skill.rename(infra_skill)
        print(f"  Renamed: plugins/.../skills/hosts -> skills/infra")
    
    website_skill = skills_dir / "websites"
    ingress_skill = skills_dir / "ingress"
    if website_skill.exists() and not ingress_skill.exists():
        website_skill.rename(ingress_skill)
        print(f"  Renamed: plugins/.../skills/websites -> skills/ingress")

# Rename ledger md files
for target in ("wsl", "prod0-main", "prod2-main"):
    old = ROOT / "inventory/servers" / target / "ledgers/websites.md"
    new = ROOT / "inventory/servers" / target / "ledgers/ingress.md"
    if old.exists() and not new.exists():
        old.rename(new)
        print(f"  Renamed: {old.relative_to(ROOT)} -> {new.relative_to(ROOT)}")

# Also update .codex and .agents skills if they exist
for dirname in (".codex", ".agents"):
    d = ROOT / dirname / "skills"
    if d.exists():
        for f in d.glob("**/*"):
            if f.is_file() and f.suffix in (".md", ".yaml", ".yml"):
                replace_in_file(f, r)

print("\n=== Done ===")
