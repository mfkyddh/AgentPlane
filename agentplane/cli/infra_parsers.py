from __future__ import annotations

import argparse

from agentplane.cli.cleanup import SUPPORTED_CLEANUP_TARGETS
from agentplane.cli.infra_automation import SUPPORTED_AUTOMATION_OPERATIONS, SUPPORTED_AUTOMATION_TARGETS
from agentplane.cli.networks import SUPPORTED_NETWORK_TARGETS
from agentplane.domain.infra.live_gate import DEFAULT_APP, DEFAULT_WSL_PROJECTION_PROFILE, LIVE_GATE_PROFILES
from agentplane.domain.infra.local import add_local_infra_parser
from agentplane.domain.targets import SUPPORTED_INFRA_TARGETS

FORMAL_INFRA_TARGETS = ("wsl", "prod0-main")

INFRA_ACTION_SCOPE_HELP = (
    "基座治理: inventory / audit / live-gate\n"
    "健康检查: health\n"
    "执行通道: remote bash\n"
    "安全配置: secrets init-data-services | sync-layout\n"
    "网络治理: network audit | ensure\n"
    "周期调度: automation search | get | verify | plan | apply\n"
    "生命周期: cleanup plan | apply\n"
    "本地: inspect"
)


def _target_help(*, scope: str, targets: tuple[str, ...]) -> str:
    return f"{scope}（可选: {', '.join(targets)}）"


def add_infra_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    if tuple(SUPPORTED_INFRA_TARGETS) != FORMAL_INFRA_TARGETS:
        raise ValueError(
            f"infra formal targets drift: expected {FORMAL_INFRA_TARGETS}, got {tuple(SUPPORTED_INFRA_TARGETS)}"
        )

    infra_parser = subparsers.add_parser(
        "infra",
        help="基础设施治理（主机、网络、Secrets、自动化）",
        description="统一 infra 治理入口（Phase 3 formal targets: wsl / prod0-main）",
        epilog=INFRA_ACTION_SCOPE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    infra_subparsers = infra_parser.add_subparsers(dest="infra_action", required=True)
    add_local_infra_parser(infra_subparsers)

    inventory_parser = infra_subparsers.add_parser("inventory", help="生成基础设施结构化清单")
    inventory_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_INFRA_TARGETS),
    )
    inventory_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    inventory_parser.add_argument("--write", action="store_true", help="写回 inventory 文件")

    audit_parser = infra_subparsers.add_parser("audit", help="执行基础设施基线审计")
    audit_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_INFRA_TARGETS),
    )
    audit_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    audit_parser.add_argument("--write", action="store_true", help="将审计结果写入操作记录")

    live_gate_parser = infra_subparsers.add_parser(
        "live-gate",
        help="独立真实 WSL/SSH/Docker live integration gate",
        description="真实 live gate 与默认 pytest 分离；run --execute 使用当前单 checkout，并按宿主路由到 WSL/SSH/Docker backend。",
    )
    live_gate_subparsers = live_gate_parser.add_subparsers(dest="infra_live_gate_action", required=True)
    for action in ("plan", "run"):
        parser = live_gate_subparsers.add_parser(action, help=f"{action} live integration gate")
        parser.add_argument("--profile", required=True, choices=LIVE_GATE_PROFILES, help="live gate profile")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        parser.add_argument("--app", default=DEFAULT_APP, help="应用验证样板 app")
        parser.add_argument(
            "--projection-profile",
            default=DEFAULT_WSL_PROJECTION_PROFILE,
            help="WSL projection verification profile",
        )
        if action == "run":
            parser.add_argument("--execute", action="store_true", help="执行真实 WSL/SSH/Docker live gate")

    cleanup_parser = infra_subparsers.add_parser("cleanup", help="执行基础设施级清理流程")
    cleanup_subparsers = cleanup_parser.add_subparsers(dest="infra_cleanup_action", required=True)
    cleanup_plan_parser = cleanup_subparsers.add_parser("plan", help="生成基础设施级清理计划")
    cleanup_plan_parser.add_argument(
        "target",
        choices=SUPPORTED_CLEANUP_TARGETS,
        help=_target_help(scope="target-specific: cleanup", targets=SUPPORTED_CLEANUP_TARGETS),
    )
    cleanup_plan_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    cleanup_apply_parser = cleanup_subparsers.add_parser("apply", help="执行白名单清理")
    cleanup_apply_parser.add_argument(
        "target",
        choices=SUPPORTED_CLEANUP_TARGETS,
        help=_target_help(scope="target-specific: cleanup", targets=SUPPORTED_CLEANUP_TARGETS),
    )
    cleanup_apply_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    automation_parser = infra_subparsers.add_parser("automation", help="基础设施自动化任务与 1Panel 调度器收口")
    automation_subparsers = automation_parser.add_subparsers(dest="infra_automation_action", required=True)
    automation_search_parser = automation_subparsers.add_parser("search", help="列出受管自动化任务")
    automation_search_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_search_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_get_parser = automation_subparsers.add_parser("get", help="读取自动化任务声明")
    automation_get_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_get_parser.add_argument("--name", required=True, help="自动化任务名称")
    automation_get_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_verify_parser = automation_subparsers.add_parser(
        "verify", help="核验自动化任务与 1Panel cronjob 是否一致"
    )
    automation_verify_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_verify_parser.add_argument("--name", required=True, help="自动化任务名称")
    automation_verify_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_verify_parser.add_argument("--env-file", help="覆盖 1Panel API env 文件")
    for action in ("plan", "apply"):
        parser = automation_subparsers.add_parser(action, help=f"{action} 自动化任务")
        parser.add_argument(
            "target",
            choices=SUPPORTED_AUTOMATION_TARGETS,
            help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
        )
        parser.add_argument("--name", required=True, help="自动化任务名称")
        parser.add_argument("--operation", required=True, choices=SUPPORTED_AUTOMATION_OPERATIONS, help="自动化操作")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        parser.add_argument("--env-file", help="覆盖 1Panel API env 文件")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行计划")

    health_parser = infra_subparsers.add_parser(
        "health",
        help="基础设施健康检查（结构化健康摘要）",
        description="查询 1Panel dashboard/monitor/alert 证据，输出结构化健康摘要",
    )
    health_parser.add_argument(
        "target",
        choices=FORMAL_INFRA_TARGETS,
        help=_target_help(scope="正式目标", targets=FORMAL_INFRA_TARGETS),
    )
    health_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    network_parser = infra_subparsers.add_parser("network", help="治理受管 Docker bridge 网络")
    network_subparsers = network_parser.add_subparsers(dest="infra_network_action", required=True)
    network_audit_parser = network_subparsers.add_parser("audit", help="审计受管 bridge 网络")
    network_audit_parser.add_argument(
        "target",
        choices=SUPPORTED_NETWORK_TARGETS,
        help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
    )
    network_audit_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    network_ensure_parser = network_subparsers.add_parser("ensure", help="修复受管 bridge 网络漂移")
    network_ensure_parser.add_argument(
        "target",
        choices=SUPPORTED_NETWORK_TARGETS,
        help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
    )
    network_ensure_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    firewall_audit_parser = network_subparsers.add_parser("firewall-audit", help="审计 1Panel 防火墙规则")
    firewall_audit_parser.add_argument(
        "target",
        choices=SUPPORTED_NETWORK_TARGETS,
        help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
    )
    firewall_audit_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    firewall_audit_parser.add_argument("--env-file", help="覆盖 1Panel API env 文件")

    firewall_parser = network_subparsers.add_parser("firewall", help="防火墙操作")
    firewall_subparsers = firewall_parser.add_subparsers(dest="infra_firewall_action", required=True)
    for action in ("plan", "apply"):
        sub = firewall_subparsers.add_parser(action, help=f"{action} firewall operation")
        sub.add_argument(
            "target",
            choices=SUPPORTED_NETWORK_TARGETS,
            help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
        )
        sub.add_argument(
            "--operation",
            required=True,
            choices=("start", "stop", "restart", "disableBanPing", "enableBanPing"),
            help="防火墙操作",
        )
        sub.add_argument("--repo-root", default=".", help="仓库根目录")
        sub.add_argument("--env-file", help="覆盖 1Panel API env 文件")
        sub.add_argument("--with-docker-restart", action="store_true", help="是否联动重启 Docker")
        if action == "apply":
            sub.add_argument("--execute", action="store_true", help="执行计划")

    remote_parser = infra_subparsers.add_parser("remote", help="基础设施远端执行入口")
    remote_subparsers = remote_parser.add_subparsers(dest="infra_remote_action", required=True)
    preflight_parser = remote_subparsers.add_parser("preflight", help="预检目标连通性与配置")
    preflight_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用 (SSH alias)", targets=FORMAL_INFRA_TARGETS),
    )
    preflight_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    bash_parser = remote_subparsers.add_parser("bash", help="通过 ssh -T 执行远端 bash")
    bash_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用 (SSH alias)", targets=FORMAL_INFRA_TARGETS),
    )
    bash_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    bash_parser.add_argument("--script-file", help="Linux 脚本文件路径")
    bash_parser.add_argument("--dry-run", action="store_true", help="只输出结构化执行计划")
    bash_parser.add_argument(
        "--intent",
        choices=("diagnostic", "read-only", "mutation"),
        default="mutation",
        help="声明命令意图 (diagnostic=诊断, read-only=只读, mutation=可修改). 默认 mutation",
    )
    bash_parser.add_argument("--stream", action="store_true", help="实时流式输出 stdout/stderr")
    bash_parser.add_argument("remote_args", nargs="*", help="透传给远端 bash -s -- 的参数")

    secrets_parser = infra_subparsers.add_parser("secrets", help="基础设施级 secrets 正式入口")
    secrets_subparsers = secrets_parser.add_subparsers(dest="infra_secrets_action", required=True)
    secrets_init_parser = secrets_subparsers.add_parser(
        "init-data-services", help="初始化 PostgreSQL/Redis/MinIO 管理员凭据"
    )
    secrets_init_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_INFRA_TARGETS),
    )
    secrets_init_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    secrets_init_parser.add_argument("--force", action="store_true", help="覆盖已存在的目标 secrets 文件")
    secrets_sync_parser = secrets_subparsers.add_parser("sync-layout", help="从 infra-first secrets 真源投影旧布局")
    secrets_sync_parser.add_argument(
        "target",
        choices=SUPPORTED_INFRA_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_INFRA_TARGETS),
    )
    secrets_sync_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    secrets_sync_parser.add_argument("--write", action="store_true", help="写入投影路径")

    bootstrap_parser = infra_subparsers.add_parser("bootstrap", help="模板仓库 bootstrap 入口")
    bootstrap_subparsers = bootstrap_parser.add_subparsers(dest="infra_bootstrap_action", required=True)
    for action in ("inspect-local", "init-secrets", "verify-secrets", "doctor"):
        parser = bootstrap_subparsers.add_parser(action, help=f"{action} bootstrap flow")
        parser.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
