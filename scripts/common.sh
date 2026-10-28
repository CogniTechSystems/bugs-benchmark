#!/usr/bin/env bash
# Shared configuration for the Linux and WSL helper scripts.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

is_wsl_windows_mount() {
  grep -qi microsoft /proc/version 2>/dev/null && [[ "$ROOT" == /mnt/* ]]
}

# A checkout on a Windows drive may also be used from Windows, so WSL keeps its virtual
# environment and data on the Linux filesystem, where SQLite locking is reliable.
if is_wsl_windows_mount; then
  VENV="${BHB_VENV:-$HOME/.venvs/bug-hunt-benchmark}"
  export BHB_DATA_DIR="${BHB_DATA_DIR:-$HOME/.local/share/bug-hunt-benchmark}"
else
  VENV="${BHB_VENV:-$ROOT/backend/.venv}"
fi
