#!/usr/bin/env bash
#
# Install the Cursor/VS Code remote tmux launcher and merge Remote SSH machine settings.
# Run on the machine where integrated terminals execute:
#   - From your Mac:  ./scripts/install-cursor-remote-tmux.sh --ssh user@host
#   - On the server:  ./scripts/install-cursor-remote-tmux.sh
#
# Does not change local macOS terminal settings unless you run this on the Mac
# (not recommended for the "remote only" workflow).
#
set -euo pipefail

DRY_RUN=0
SSH_TARGET=""

usage() {
  sed -n '1,20p' "$0" | tail -n +2
  echo "Usage: $0 [--dry-run] [--ssh user@host]"
  echo "  (no args)   Install on this machine (typical: run after SSH login on server)."
  echo "  --ssh HOST  Run the full install remotely over SSH."
  echo "  --dry-run   Print actions without writing files."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --ssh)
      SSH_TARGET="${2:-}"
      [[ -n "$SSH_TARGET" ]] || { echo "error: --ssh requires user@host" >&2; exit 1; }
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

write_launcher() {
  local dest="$1"
  run mkdir -p "$(dirname "$dest")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would write launcher to $dest"
    return 0
  fi
  cat > "$dest" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# Cursor/VS Code integrated terminal tmux launcher (bash 3.2 / macOS compatible)

if [[ -z "${TERM_PROGRAM:-}" ]] || [[ "$TERM_PROGRAM" != "vscode" ]]; then
  exec "${SHELL:-/bin/bash}" -l
fi

if [[ -n "${TMUX:-}" ]]; then
  exec "${SHELL:-/bin/bash}" -l
fi

if ! command -v tmux >/dev/null 2>&1; then
  exec "${SHELL:-/bin/bash}" -l
fi

sessions=()
while IFS= read -r line; do
  [[ -n "$line" ]] && sessions+=("$line")
done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)

if [[ ${#sessions[@]} -eq 0 ]]; then
  exec tmux new-session -s cursor
fi

echo "Existing tmux session(s): ${sessions[*]}"
echo "1) Attach to first session: ${sessions[0]}"
echo "2) Kill all tmux sessions and start a new one named 'cursor'"
echo "3) Skip tmux (plain shell)"
read -r -p "Choose [1-3] (default 1): " choice
choice=${choice:-1}

case "$choice" in
  1) exec tmux attach-session -t "${sessions[0]}" ;;
  2) tmux kill-server; exec tmux new-session -s cursor ;;
  3) exec "${SHELL:-/bin/bash}" -l ;;
  *) exec tmux attach-session -t "${sessions[0]}" ;;
esac
LAUNCHER_EOF
  chmod +x "$dest"
}

merge_remote_settings() {
  local launcher_path="$1"
  local settings_path="$2"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would merge terminal profile into $settings_path"
    return 0
  fi

  python3 - "$launcher_path" "$settings_path" << 'PY'
import json
import os
import sys

launcher = sys.argv[1]
path = sys.argv[2]
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {}
if os.path.isfile(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

profile_key = "terminal.integrated.profiles.linux"
default_key = "terminal.integrated.defaultProfile"

profiles = data.get(profile_key)
if not isinstance(profiles, dict):
    profiles = {}
    data[profile_key] = profiles

profiles["tmux-menu"] = {
    "path": "/bin/bash",
    "args": ["-l", "-c", f"exec {launcher}"],
    "icon": "terminal-tmux",
}

data[default_key] = "tmux-menu"

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=False)
    f.write("\n")
PY
}

install_on_this_machine() {
  local home_bin="${HOME}/bin"
  local launcher="${home_bin}/cursor-tmux-launcher.sh"
  write_launcher "$launcher"

  # Prefer Cursor remote path; also mirror to VS Code server if present (some setups).
  local cursor_machine="${HOME}/.cursor-server/data/Machine/settings.json"
  local vscode_machine="${HOME}/.vscode-server/data/Machine/settings.json"

  merge_remote_settings "$launcher" "$cursor_machine"
  if [[ -d "$(dirname "$vscode_machine")" ]]; then
    merge_remote_settings "$launcher" "$vscode_machine"
  fi

  echo "Installed:"
  echo "  Launcher: $launcher"
  echo "  Settings: $cursor_machine"
  if [[ -d "$(dirname "$vscode_machine")" ]]; then
    echo "  (also)    $vscode_machine"
  fi
  echo "Reconnect the Remote SSH window or open a new integrated terminal to use tmux-menu."
}

remote_install_body() {
  # Script chunk executed on remote (bash).
  cat << 'REMOTE_EOF'
set -euo pipefail
HOME_BIN="${HOME}/bin"
LAUNCHER="${HOME_BIN}/cursor-tmux-launcher.sh"
mkdir -p "$HOME_BIN"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# Cursor/VS Code integrated terminal tmux launcher (bash 3.2 / macOS compatible)

if [[ -z "${TERM_PROGRAM:-}" ]] || [[ "$TERM_PROGRAM" != "vscode" ]]; then
  exec "${SHELL:-/bin/bash}" -l
fi

if [[ -n "${TMUX:-}" ]]; then
  exec "${SHELL:-/bin/bash}" -l
fi

if ! command -v tmux >/dev/null 2>&1; then
  exec "${SHELL:-/bin/bash}" -l
fi

sessions=()
while IFS= read -r line; do
  [[ -n "$line" ]] && sessions+=("$line")
done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)

if [[ ${#sessions[@]} -eq 0 ]]; then
  exec tmux new-session -s cursor
fi

echo "Existing tmux session(s): ${sessions[*]}"
echo "1) Attach to first session: ${sessions[0]}"
echo "2) Kill all tmux sessions and start a new one named 'cursor'"
echo "3) Skip tmux (plain shell)"
read -r -p "Choose [1-3] (default 1): " choice
choice=${choice:-1}

case "$choice" in
  1) exec tmux attach-session -t "${sessions[0]}" ;;
  2) tmux kill-server; exec tmux new-session -s cursor ;;
  3) exec "${SHELL:-/bin/bash}" -l ;;
  *) exec tmux attach-session -t "${sessions[0]}" ;;
esac
LAUNCHER_EOF
chmod +x "$LAUNCHER"
command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required on the remote host" >&2; exit 1; }
python3 - "$LAUNCHER" "${HOME}/.cursor-server/data/Machine/settings.json" << 'PY'
import json
import os
import sys

launcher = sys.argv[1]
path = sys.argv[2]
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {}
if os.path.isfile(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
profile_key = "terminal.integrated.profiles.linux"
default_key = "terminal.integrated.defaultProfile"
profiles = data.get(profile_key)
if not isinstance(profiles, dict):
    profiles = {}
    data[profile_key] = profiles
profiles["tmux-menu"] = {
    "path": "/bin/bash",
    "args": ["-l", "-c", f"exec {launcher}"],
    "icon": "terminal-tmux",
}
data[default_key] = "tmux-menu"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=False)
    f.write("\n")
PY
VS_MACHINE="${HOME}/.vscode-server/data/Machine/settings.json"
if [[ -d "$(dirname "$VS_MACHINE")" ]]; then
  python3 - "$LAUNCHER" "$VS_MACHINE" << 'PY'
import json
import os
import sys
launcher = sys.argv[1]
path = sys.argv[2]
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {}
if os.path.isfile(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
profile_key = "terminal.integrated.profiles.linux"
default_key = "terminal.integrated.defaultProfile"
profiles = data.get(profile_key)
if not isinstance(profiles, dict):
    profiles = {}
    data[profile_key] = profiles
profiles["tmux-menu"] = {
    "path": "/bin/bash",
    "args": ["-l", "-c", f"exec {launcher}"],
    "icon": "terminal-tmux",
}
data[default_key] = "tmux-menu"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=False)
    f.write("\n")
PY
fi
echo "Remote install done: $LAUNCHER"
REMOTE_EOF
}

main() {
  if [[ -n "$SSH_TARGET" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "[dry-run] would: ssh $SSH_TARGET bash -s < remote_install_body"
      exit 0
    fi
    # shellcheck disable=SC2029
    ssh "$SSH_TARGET" "bash -s" < <(remote_install_body)
    echo "Installed on $SSH_TARGET. Reconnect Remote SSH or open a new terminal."
    exit 0
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 is required to merge JSON settings" >&2
    exit 1
  fi

  install_on_this_machine
}

main "$@"
