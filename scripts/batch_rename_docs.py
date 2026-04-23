"""Batch update documentation files for AgentPlane 4-domain refactoring."""
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

doc_replacements = {
    # Command references
    "agentplane host ": "agentplane infra ",
    "agentplane website ": "agentplane ingress ",
    "agentplane projection ": "agentplane projection ",  # keep for now
    "agentplane onepanel ": "agentplane onepanel ",  # keep for now
    # Domain names in prose
    "`host`": "`infra`",
    "`website`": "`ingress`",
    "**host**": "**infra**",
    "**website**": "**ingress**",
    # Common phrases
    "基础设施治理（主机、网络、Secrets、自动化）": "基础设施治理（主机、网络、Secrets、自动化）",
    "主机基线审计": "基础设施基线审计",
    "主机级清理": "基础设施级清理",
    "主机自动化": "基础设施自动化",
    "主机远端": "基础设施远端",
    "主机级 secrets": "基础设施级 secrets",
    "基础设施级治理": "基础设施级治理",
    "正式公网入口对象": "公网入口对象（HTTP 与非 HTTP）",
    "网站对象": "入口对象",
    "网站别名": "入口别名",
    "网站验证": "入口验证",
    "受管网站": "受管入口",
    "5 个对象域": "4 个对象域 + 横切机制",
    "5 个\"对象域\"": "4 个对象域 + 横切机制",
    "5个对象域": "4个对象域+横切机制",
    # Specific table/command references
    "host inventory": "infra inventory",
    "host audit": "infra audit",
    "host cleanup": "infra cleanup",
    "host automation": "infra automation",
    "host network": "infra network",
    "host remote bash": "infra remote bash",
    "host secrets": "infra secrets",
    "host local": "infra local",
    "host live-gate": "infra live-gate",
    "website search": "ingress search",
    "website get": "ingress get",
    "website verify": "ingress verify",
    "website plan": "ingress plan",
    "website apply": "ingress apply",
    "website publish": "ingress publish",
    "website refresh-ledger": "ingress refresh-ledger",
    "website reconcile": "ingress reconcile",
    "双轨真源模型": "真源与三层状态模型",
    # Terms
    "SUPPORTED_INFRA_TARGETS": "SUPPORTED_INFRA_TARGETS",
    "SUPPORTED_INGRESS_TARGETS": "SUPPORTED_INGRESS_TARGETS",
    "InfraAutomationDefinition": "InfraAutomationDefinition",
    "IngressDefinition": "IngressDefinition",
    "IngressFollowThrough": "IngressFollowThrough",
}

# Process all markdown files
md_files = list(ROOT.glob("docs/**/*.md")) + list(ROOT.glob("*.md"))
print(f"Found {len(md_files)} markdown files to process")
for f in md_files:
    if f.is_file():
        replace_in_file(f, doc_replacements)

# Process AGENTS.md specifically (it has more specific patterns)
agents = ROOT / "AGENTS.md"
if agents.exists():
    c = agents.read_text(encoding="utf-8")
    # AGENTS.md has specific table entries
    c = c.replace("| `host` |", "| `infra` |")
    c = c.replace("| `website` |", "| `ingress` |")
    c = c.replace("| `projection` |", "| 横切机制 |")
    c = c.replace("agentplane host", "agentplane infra")
    c = c.replace("agentplane website", "agentplane ingress")
    c = c.replace("agentplane projection", "agentplane projection")  # keep
    agents.write_text(c, encoding="utf-8")
    print(f"  Updated: AGENTS.md (specific patterns)")

print("\n=== Done ===")
