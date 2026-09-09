#!/usr/bin/env bash
# Print the project-relative path to the architecture-specific venv directory
# (e.g. .venv-darwin-arm64) for use with UV_PROJECT_ENVIRONMENT or symlinks.
# Must stay in sync with get_platform_venv_path() in reproduce_environment_comp_uv.sh
set -euo pipefail

platform=""
arch="$(uname -m)"

case "$(uname -s)" in
  Darwin) platform="darwin" ;;
  Linux)  platform="linux" ;;
  *)      echo ".venv"; exit 0 ;;
esac

if [[ "$(uname -s)" == "Darwin" ]]; then
  if sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
    arch="arm64"
  else
    arch="x86_64"
  fi
fi

case "$arch" in
  arm64)   norm="arm64" ;;
  aarch64) norm="aarch64" ;;
  x86_64)  norm="x86_64" ;;
  *)       norm="$arch" ;;
esac

if [[ -n "$platform" ]] && [[ -n "$norm" ]]; then
  echo ".venv-${platform}-${norm}"
else
  echo ".venv"
fi
