#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${OS:-}:$(uname -s)" in
  Windows_NT:*|*:MINGW*|*:MSYS*|*:CYGWIN*)
    exec pwsh -NoProfile -ExecutionPolicy Bypass -File "$script_dir/setup.windows.ps1"
    ;;
esac

exec bash "$script_dir/setup.linux.sh"
