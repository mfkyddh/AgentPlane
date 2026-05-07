from __future__ import annotations

import argparse
from pathlib import Path


def add_web_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    web_parser = subparsers.add_parser("web", help="启动 AgentPlane WebUI")
    web_parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8080, help="端口 (默认 8080)")
    web_parser.add_argument("--token", default=None, help="预共享 token (可选)")
    web_parser.add_argument("--repo-root", default=".", help="仓库根目录")


def handle_web_command(args: argparse.Namespace) -> int:
    import uvicorn

    from agentplane.web.server import create_app

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"Error: repo-root does not exist: {repo_root}")
        return 1
    if not (repo_root / "inventory").is_dir():
        print(f"Error: repo-root missing 'inventory/' directory: {repo_root}")
        return 1

    token = args.token or None

    app = create_app(repo_root=repo_root, token=token)

    print(f"AgentPlane WebUI starting on http://{args.host}:{args.port}")
    if token:
        print("Authentication enabled (token required)")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
