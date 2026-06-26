from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import get_app, search_apps, verify_app_object
from agentplane.domain.targets import FORMAL_TARGETS

logger = logging.getLogger(__name__)

ALLOWED_VERBS = {"search", "get", "verify"}
BLOCKED_VERBS = {"apply", "delete", "plan", "migrate", "deploy", "rollback"}
CONFIRM_VERBS = {"plan", "apply"}

COMMAND_MAP = {
    "app search": lambda repo_root, args: search_apps(repo_root, *args),
    "app get": lambda repo_root, args: get_app(repo_root, *args),
    "app verify": lambda repo_root, args: verify_app_object(repo_root, *args),
}

EXPECTED_ARG_COUNTS = {
    "app search": 1,
    "app get": 2,
    "app verify": 2,
}

SYSTEM_PROMPT = """You are AgentPlane's AI assistant for server infrastructure management.
You can execute read-only commands to check status and health.

Available commands (respond with JSON):
- {"command": "app search", "args": ["<target>"]} — list all apps for a target
- {"command": "app get", "args": ["<target>", "<app_name>"]} — get app details
- {"command": "app verify", "args": ["<target>", "<app_name>"]} — verify app object

Targets: "wsl" or "prod0-main"

FORBIDDEN commands (never generate these):
- apply, delete, plan, migrate, deploy, rollback
- Any shell commands
- Any destructive operations

If the user asks for something destructive, respond with:
{"command": "blocked", "reason": "This is a destructive operation. Please use the CLI: agentplane <command>"}

Always respond with valid JSON only. No markdown, no explanation outside JSON."""


async def call_llm(user_message: str, history: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"command": "error", "reason": "ANTHROPIC_API_KEY not set"}

    text = ""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        messages = [*history, {"role": "user", "content": user_message}]
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        text = response.content[0].text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %s", text[:500])
        return {"command": "error", "reason": "LLM returned invalid JSON. Please try again."}
    except Exception as exc:
        logger.error("LLM call failed: %s", exc, exc_info=True)
        return {"command": "error", "reason": "LLM call failed. Please try again."}


def validate_command(cmd: dict[str, Any]) -> dict[str, Any]:
    command = cmd.get("command", "")
    if command in ("blocked", "error"):
        return cmd

    parts = command.split()
    if len(parts) < 2:
        return {"command": "error", "reason": f"Invalid command format: {command}"}

    verb = parts[-1]
    if verb in CONFIRM_VERBS:
        return {
            "command": "needs_confirmation",
            "original_command": command,
            "args": cmd.get("args", []),
            "reason": f"Write operation '{verb}' requires confirmation. Reply 'yes' to proceed.",
        }
    if verb in BLOCKED_VERBS:
        return {
            "command": "blocked",
            "reason": f"Destructive operation '{verb}' is not allowed in WebUI. Use CLI: agentplane {command}",
        }
    if verb not in ALLOWED_VERBS:
        return {"command": "error", "reason": f"Unknown verb: {verb}. Allowed: {', '.join(sorted(ALLOWED_VERBS))}"}

    args = cmd.get("args", [])
    expected = EXPECTED_ARG_COUNTS.get(command)
    if expected is not None and len(args) != expected:
        return {"command": "error", "reason": f"Expected {expected} args for '{command}', got {len(args)}"}

    if args and args[0] not in FORMAL_TARGETS:
        return {"command": "error", "reason": f"Invalid target: {args[0]}. Must be one of: {', '.join(FORMAL_TARGETS)}"}

    return cmd


def execute_command(repo_root: Path, cmd: dict[str, Any]) -> dict[str, Any]:
    command = cmd.get("command", "")
    args = cmd.get("args", [])

    handler = COMMAND_MAP.get(command)
    if not handler:
        return {"status": "error", "message": f"No handler for command: {command}"}

    try:
        result = handler(repo_root, args)
        return {"status": "success", "command": command, "output": result}
    except (ValueError, FileNotFoundError, KeyError) as exc:
        return {"status": "error", "command": command, "message": str(exc)}
    except Exception as exc:
        logger.error("Command execution failed: %s %s", command, exc, exc_info=True)
        return {"status": "error", "command": command, "message": "Internal error during command execution"}


async def handle_chat_message(
    repo_root: Path,
    user_message: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    llm_response = await call_llm(user_message, history)
    validated = validate_command(llm_response)

    if validated.get("command") == "needs_confirmation":
        return {
            "type": "confirmation_required",
            "payload": validated,
        }

    if validated.get("command") in ("blocked", "error"):
        return {
            "type": "command_rejected" if validated["command"] == "blocked" else "error",
            "payload": validated,
        }

    result = execute_command(repo_root, validated)
    return {"type": "command_result", "payload": result}
