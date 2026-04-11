from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.scripts.automation.backup_secrets_r2 import DEFAULT_ENV_FILE
from agentplane.scripts.automation.backup_secrets_r2 import DEFAULT_TASK_ENV_FILE
from agentplane.scripts.automation.backup_secrets_r2 import ensure_onepanel_task
from agentplane.scripts.automation.backup_secrets_r2 import load_config
from agentplane.scripts.automation.backup_secrets_r2 import run_backup
from agentplane.scripts.automation.sync_zzz_skills import run_sync


def add_automation_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    automation_parser = subparsers.add_parser("automation", help="本机自动化任务")
    automation_subparsers = automation_parser.add_subparsers(dest="automation_action", required=True)

    sync = automation_subparsers.add_parser(
        "sync-zzz-skills",
        help="同步当前会话挂载的 CODEX_HOME 中 zzz-* 技能到 zzz-skills 仓库",
    )
    sync.add_argument(
        "--source-root",
        default="/mnt/c/Users/Administrator/.codex/skills",
        help="技能源目录；默认使用当前会话挂载的 CODEX_HOME（/mnt/c/Users/Administrator/.codex/skills）",
    )
    sync.add_argument("--target-repo", default="/root/work/zzz-skills", help="目标 Git 仓库")
    sync.add_argument("--branch", default="main", help="目标分支")

    backup = automation_subparsers.add_parser("backup-secrets-r2", help="加密备份 secrets 目录到 Cloudflare R2")
    backup.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="R2 备份配置 env 文件")

    ensure_task = automation_subparsers.add_parser(
        "ensure-secrets-backup-cronjob",
        help="创建或更新 WSL 本机 1Panel secrets 备份计划任务",
    )
    ensure_task.add_argument("--env-file", default=str(DEFAULT_TASK_ENV_FILE), help="1Panel API env 文件")
    ensure_task.add_argument("--trigger-now", action="store_true", help="创建或更新后立刻手动触发一次")


def handle_automation_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.automation_action == "sync-zzz-skills":
        payload = run_sync(
            source_root=Path(args.source_root),
            target_repo=Path(args.target_repo),
            branch=args.branch,
        )
        return {"command": "automation", "action": "sync-zzz-skills", "payload": payload}
    if args.automation_action == "backup-secrets-r2":
        payload = run_backup(load_config(Path(args.env_file)))
        return {"command": "automation", "action": "backup-secrets-r2", "payload": payload}
    if args.automation_action == "ensure-secrets-backup-cronjob":
        payload = ensure_onepanel_task(env_file=Path(args.env_file), trigger_now=bool(args.trigger_now))
        return {"command": "automation", "action": "ensure-secrets-backup-cronjob", "payload": payload}
    raise ValueError(f"Unsupported automation action: {args.automation_action}")
