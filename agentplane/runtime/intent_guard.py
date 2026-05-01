from __future__ import annotations

from typing import Literal

Intent = Literal["diagnostic", "read-only", "mutation"]


class IntentGuardViolation(ValueError):
    """Declared intent is stricter than the inferred intent of the command."""


# Commands that are typically read-only (but may mutate with certain flags).
_READ_ONLY_COMMANDS = frozenset(
    {
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "find",
        "ls",
        "stat",
        "file",
        "id",
        "whoami",
        "hostname",
        "env",
        "printenv",
        "pwd",
        "echo",
        "which",
        "whereis",
        "ps",
        "top",
        "htop",
        "df",
        "du",
        "free",
        "uptime",
        "uname",
        "dmesg",
        "ss",
        "netstat",
        "lsof",
        "ping",
        "curl",
        "wget",
        "tar",
        "cp",
        "scp",
        "rsync",
        "git",
        "journalctl",
        "systemctl",
        "docker",
    }
)

# Commands or tokens that strongly indicate a mutation.
_MUTATION_COMMANDS = frozenset(
    {
        "rm",
        "rmdir",
        "shred",
        "mkfs",
        "fdisk",
        "parted",
        "dd",
        "truncate",
        "fallocate",
        "chmod",
        "chown",
        "chgrp",
        "setfacl",
        "mv",
        "rename",
        "apt",
        "apt-get",
        "yum",
        "dnf",
        "pacman",
        "pip",
        "npm",
        "yarn",
        "gem",
        "cargo",
        "make",
        "cmake",
        "ninja",
        "install",
        "useradd",
        "usermod",
        "userdel",
        "groupadd",
        "groupmod",
        "groupdel",
        "passwd",
        "ssh-keygen",
        "mount",
        "umount",
    }
)

# Flags that turn a read-only command into a mutation.
_MUTATION_FLAGS = frozenset({"-i", "--in-place", "-o", "-O", "-c", "--create"})

# Shell redirection or pipeline tokens that imply writing.
_MUTATION_TOKENS = frozenset({">", ">>", ">|", "tee", "xargs"})


def _token_is_mutation(token: str) -> bool:
    """Check whether a single token indicates mutation."""
    if token in _MUTATION_COMMANDS:
        return True
    if token in _MUTATION_TOKENS:
        return True
    # Detect redirections like >file, >>file
    if token.startswith(">") and len(token) > 1:
        return True
    return False


def _has_mutation_tokens(tokens: list[str]) -> bool:
    """Scan a token list for any mutation indicator."""
    return any(_token_is_mutation(t) for t in tokens)


def _is_read_only_docker(argv: tuple[str, ...]) -> bool:
    """docker ps / images / inspect / logs / network ls / volume ls are read-only."""
    if len(argv) < 2:
        return False
    safe_subcommands = frozenset(
        {
            "ps",
            "images",
            "inspect",
            "logs",
            "top",
            "stats",
            "port",
            "diff",
            "history",
            "info",
            "version",
            "search",
        }
    )
    if argv[1] in safe_subcommands:
        return True
    # docker network ls / docker volume ls / docker compose config
    if len(argv) >= 3 and argv[1] in ("network", "volume", "compose") and argv[2] in ("ls", "inspect", "config"):
        return True
    return False


def _is_read_only_systemctl(argv: tuple[str, ...]) -> bool:
    """systemctl status / list-units / show are read-only."""
    if len(argv) < 2:
        return False
    safe_subcommands = frozenset({"status", "list-units", "list-timers", "show", "cat", "is-active", "is-enabled"})
    return argv[1] in safe_subcommands


def _is_read_only_git(argv: tuple[str, ...]) -> bool:
    """git status / log / diff / show are read-only."""
    if len(argv) < 2:
        return False
    safe_subcommands = frozenset({"status", "log", "diff", "show", "branch", "remote", "config"})
    return argv[1] in safe_subcommands


def analyze_intent(argv: tuple[str, ...]) -> Intent:
    """Infer the likely intent from the command arguments.

    Returns the *most conservative* (least permissive) intent that matches.
    Unknown commands default to ``mutation``.
    """
    if not argv:
        return "read-only"

    cmd = argv[0]
    tokens = list(argv)

    # Shell wrappers – intent depends on stdin script content
    if cmd in ("bash", "sh", "zsh", "dash"):
        if _has_mutation_tokens(tokens):
            return "mutation"
        return "read-only"

    # Docker – whitelist read-only subcommands; everything else is mutation
    if cmd == "docker":
        if _is_read_only_docker(argv):
            return "read-only"
        return "mutation"

    # systemctl – whitelist read-only subcommands; everything else is mutation
    if cmd == "systemctl":
        if _is_read_only_systemctl(argv):
            return "diagnostic"
        return "mutation"

    # git – whitelist read-only subcommands; everything else is mutation
    if cmd == "git":
        if _is_read_only_git(argv):
            return "read-only"
        return "mutation"

    # Check for mutation flags on read-only commands
    if cmd in _READ_ONLY_COMMANDS:
        if any(t in _MUTATION_FLAGS for t in tokens):
            return "mutation"
        if _has_mutation_tokens(tokens):
            return "mutation"
        return "read-only"

    # Known mutation commands
    if cmd in _MUTATION_COMMANDS:
        return "mutation"

    # Fallback: scan all tokens for mutation indicators
    if _has_mutation_tokens(tokens):
        return "mutation"

    # Unknown command – treat as mutation to be safe
    return "mutation"


def _analyze_stdin_text(stdin_text: str | None) -> Intent:
    """Infer intent from a shell script body passed via stdin."""
    if not stdin_text:
        return "read-only"
    tokens = stdin_text.split()
    if _has_mutation_tokens(tokens):
        return "mutation"
    return "read-only"


def guard(
    declared: Intent,
    *,
    argv: tuple[str, ...],
    stdin_text: str | None = None,
) -> None:
    """Validate that *declared* intent is not stricter than the inferred intent.

    Raises:
        IntentGuardViolation: If the declared intent is more restrictive than
        what the command arguments (and optional stdin script) imply.
    """
    if declared == "mutation":
        return

    inferred_argv = analyze_intent(argv)

    # Take the more permissive (less safe) of the two inferences
    inferred = inferred_argv
    if stdin_text is not None:
        inferred_stdin = _analyze_stdin_text(stdin_text)
        if inferred_stdin == "mutation" or inferred == "mutation":
            inferred = "mutation"
        elif inferred_stdin == "read-only" or inferred == "read-only":
            inferred = "read-only"
        else:
            inferred = "diagnostic"

    if declared == "diagnostic" and inferred in ("read-only", "mutation"):
        raise IntentGuardViolation(
            f"intent mismatch: declared 'diagnostic' but command is inferred as "
            f"'{inferred}'. Use --intent={inferred} or --intent=mutation."
        )

    if declared == "read-only" and inferred == "mutation":
        raise IntentGuardViolation(
            "intent mismatch: declared 'read-only' but command is inferred as 'mutation'. Use --intent=mutation."
        )
