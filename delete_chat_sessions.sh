#!/usr/bin/env bash
#
# delete_chat_sessions.sh
#
# Delete the past Claude Code chat-session transcripts for THIS project,
# while preserving:
#   - the currently-active session (if run from inside Claude Code)
#   - the persistent ./memory/ directory
#   - any non-.jsonl files
#
# Session transcripts live as <uuid>.jsonl files under:
#   ~/.claude/projects/<encoded-project-path>/
#
# Usage:
#   bash delete_chat_sessions.sh           # interactive: lists, then asks to confirm
#   bash delete_chat_sessions.sh --yes     # skip the confirmation prompt
#   bash delete_chat_sessions.sh --dry-run # show what would be deleted, delete nothing

set -euo pipefail

SESSION_DIR="${HOME}/.claude/projects/-Volumes-Sync-GitHub-llorracc-HAFiscal-Latest"

ASSUME_YES=0
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y)    ASSUME_YES=1 ;;
    --dry-run|-n) DRY_RUN=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -d "$SESSION_DIR" ]]; then
  echo "Session directory not found: $SESSION_DIR" >&2
  exit 1
fi

# Protect the live session if we're running inside Claude Code.
CURRENT="${CLAUDE_CODE_SESSION_ID:-}"

# Collect candidate transcripts (top-level .jsonl only; never recurse into memory/).
shopt -s nullglob
candidates=()
for f in "$SESSION_DIR"/*.jsonl; do
  base="$(basename "$f")"
  if [[ -n "$CURRENT" && "$base" == "${CURRENT}.jsonl" ]]; then
    echo "Skipping current session: $base"
    continue
  fi
  candidates+=("$f")
done

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "No past sessions to delete."
  exit 0
fi

echo
echo "The following ${#candidates[@]} past session(s) will be deleted:"
for f in "${candidates[@]}"; do
  printf '  %s  (%s)\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
done
echo

if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry run — nothing deleted."
  exit 0
fi

if [[ $ASSUME_YES -ne 1 ]]; then
  read -r -p "Delete these files? This cannot be undone. [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

for f in "${candidates[@]}"; do
  rm -f -- "$f"
  echo "Deleted $(basename "$f")"
done

echo "Done."
