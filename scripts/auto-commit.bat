@echo off
REM Auto-commit script for AgentPlane (Windows)
REM Usage:
REM   scripts\auto-commit.bat                    REM Auto-detect and commit
REM   scripts\auto-commit.bat --dry-run          REM Preview without committing
REM   scripts\auto-commit.bat --message "msg"    REM Custom message

python scripts\auto-commit.py %*
