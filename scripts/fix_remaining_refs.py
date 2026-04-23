"""全面修复所有文件中残留的旧术语引用。"""
import pathlib

ROOT = pathlib.Path(r"d:\Projects\AgentPlane")

# 全局替换映射（按长度降序排列，避免短串先匹配导致长串被截断）
GLOBAL_REPLACEMENTS = [
    # CLI 命令字符串
    ('"infra"', '"infra"'),
    ('"ingress"', '"ingress"'),
    ("'infra'", "'infra'"),
    ("'ingress'", "'ingress'"),
    # argparse dest 名称
    ("infra_action", "infra_action"),
    ("ingress_action", "ingress_action"),
    ("infra_local_action", "infra_local_action"),
    ("infra_cleanup_action", "infra_cleanup_action"),
    ("infra_automation_action", "infra_automation_action"),
    ("infra_network_action", "infra_network_action"),
    ("infra_remote_action", "infra_remote_action"),
    ("infra_secrets_action", "infra_secrets_action"),
    ("infra_live_gate_action", "infra_live_gate_action"),
    ("ingress_publish_action", "ingress_publish_action"),
    # 变量名
    ("SUPPORTED_INFRA_TARGETS", "SUPPORTED_INFRA_TARGETS"),
    ("SUPPORTED_INGRESS_TARGETS", "SUPPORTED_INGRESS_TARGETS"),
    ("public_ingresses", "public_ingresses"),
    ("infra_parser", "infra_parser"),
    ("infra_subparsers", "infra_subparsers"),
    ("ingress_parser", "ingress_parser"),
    ("ingress_subparsers", "ingress_subparsers"),
    # 类名
    ("InfraAutomationDefinition", "InfraAutomationDefinition"),
    ("IngressDefinition", "IngressDefinition"),
    ("IngressFollowThrough", "IngressFollowThrough"),
    # 函数名
    ("add_infra_parser", "add_infra_parser"),
    ("add_ingress_parser", "add_ingress_parser"),
    ("add_local_infra_parser", "add_local_infra_parser"),
    ("handle_infra_command", "handle_infra_command"),
    ("handle_ingress_command", "handle_ingress_command"),
    ("handle_local_infra_command", "handle_local_infra_command"),
    ("search_infra_automations", "search_infra_automations"),
    ("get_infra_automation", "get_infra_automation"),
    ("plan_infra_automation", "plan_infra_automation"),
    ("apply_infra_automation", "apply_infra_automation"),
    ("verify_infra_automation", "verify_infra_automation"),
    ("search_ingresses", "search_ingresses"),
    ("get_ingress", "get_ingress"),
    ("plan_ingress_operation", "plan_ingress_operation"),
    ("apply_ingress_operation", "apply_ingress_operation"),
    ("verify_ingress", "verify_ingress"),
    ("refresh_ingress_ledger", "refresh_ingress_ledger"),
    ("build_ingress_follow_through", "build_ingress_follow_through"),
    ("available_ingresses", "available_ingresses"),
    ("resolve_ingress", "resolve_ingress"),
    ("resolve_ingress_verification_profile", "resolve_ingress_verification_profile"),
    ("INGRESS_VERIFICATION_PROFILE_BY_TARGET", "INGRESS_VERIFICATION_PROFILE_BY_TARGET"),
    # import 路径
    ("from agentplane.domain.infra.", "from agentplane.domain.infra."),
    ("from agentplane.domain.ingress.", "from agentplane.domain.ingress."),
    ("from agentplane.domain.app.projection.runtime_env", "from agentplane.domain.app.projection.runtime_env"),
    ("from agentplane.cli.infra_automation", "from agentplane.cli.infra_automation"),
    ("from agentplane.cli.local_infra", "from agentplane.cli.local_infra"),
    ("from agentplane.cli.infra ", "from agentplane.cli.infra "),
    ("from agentplane.cli.ingress", "from agentplane.cli.ingress"),
    ("from agentplane.cli.infra_onepanel", "from agentplane.cli.infra_onepanel"),
    ("agentplane.domain.infra.", "agentplane.domain.infra."),
    ("agentplane.domain.ingress.", "agentplane.domain.ingress."),
    ("agentplane.domain.app.projection.runtime_env", "agentplane.domain.app.projection.runtime_env"),
    ("agentplane.cli.infra_automation", "agentplane.cli.infra_automation"),
    ("agentplane.cli.local_infra", "agentplane.cli.local_infra"),
    ("agentplane.cli.infra ", "agentplane.cli.infra "),
    ("agentplane.cli.ingress", "agentplane.cli.ingress"),
    ("agentplane.cli.infra_onepanel", "agentplane.cli.infra_onepanel"),
    # 描述文本
    ("基础设施治理（主机、网络、Secrets、自动化）", "基础设施治理（主机、网络、Secrets、自动化）"),
    ("Ingress 发布/下线", "Ingress 发布/下线"),
    ("Ingress 发布与治理", "Ingress 发布与治理"),
    ("基础设施治理", "基础设施治理"),
    ("Ingress 治理", "Ingress 治理"),
    ("基础设施级治理", "基础设施级治理"),
]

# 排除的路径（脚本自身、.git、.venv 等）
EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".workbuddy", "local"}

# 文件扩展名
INCLUDE_EXTENSIONS = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".sh", ".example"}

count = 0
for f in ROOT.rglob("*"):
    if not f.is_file():
        continue
    if any(part in EXCLUDE_DIRS for part in f.relative_to(ROOT).parts):
        continue
    if f.suffix not in INCLUDE_EXTENSIONS:
        continue

    try:
        content = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        continue

    original = content
    for old, new in GLOBAL_REPLACEMENTS:
        content = content.replace(old, new)

    if content != original:
        f.write_text(content, encoding="utf-8")
        rel = f.relative_to(ROOT)
        print(f"Updated: {rel}")
        count += 1

print(f"\nTotal files updated: {count}")
