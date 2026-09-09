#!/usr/bin/env bash
# econark-sync.sh -- pull the latest upstream copy of allowlisted @resources files at build time.
#
# Why this exists (2026-08-30): the vendored econark-shortcuts.sty had drifted five months behind
# econ-ark/econ-ark-tools (357 lines vs 574; \providecommand, which yields, where upstream had moved
# to \ARKcommand, which forces). On this machine $TEXMFLOCAL is symlinked to the econ-ark-tools
# checkout so the build never saw the stale copy -- but on a machine without that symlink kpsewhich
# finds the vendored one, and the document renders differently with no error. Silent cross-machine
# divergence is exactly what the single-dialect ruling exists to prevent.
#
# DEFAULT-DENY. Only paths in @local/econark-sync.allow are touched, and PROTECTED paths are refused
# even if listed. This is deliberately NOT @resources/scripts/@resources-update-from-remote.sh, which
# rewrites ~30 files wholesale and would revert local fixes (CLAUDE.md).
#
# "Latest" means origin/master, not the clone's working tree -- the local checkout is often on a
# feature branch (it was on notation-20260716-psav-editorial-macros when this was written).
#
# Env:
#   ECONARK_SYNC=0          disable entirely
#   ECONARK_TOOLS_REPO      explicit path to an econ-ark-tools checkout
#   ECONARK_SYNC_MAXAGE     seconds between network fetches (default 3600; 0 = every run)
#   ECONARK_SYNC_REMOTE=0   never touch the network (clone-only)
#   ECONARK_SYNC_STRICT=1   exit non-zero on failure (default: warn and succeed, so a broken
#                           network or a missing clone never blocks a document build)
set -uo pipefail

[ "${ECONARK_SYNC:-1}" = "0" ] && { echo "[econark-sync] disabled (ECONARK_SYNC=0)"; exit 0; }

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ALLOW="$ROOT/@local/econark-sync.allow"
STAMP="${TMPDIR:-/tmp}/.econark-sync-stamp-$(id -u)"
RAW="https://raw.githubusercontent.com/econ-ark/econ-ark-tools/master"
STRICT="${ECONARK_SYNC_STRICT:-0}"
RC=0

# Files with deliberate LOCAL divergence: never overwrite, whatever the allowlist says.
PROTECTED=("@resources/texlive/texmf-local/tex/latex/econark-bibfilesfind.sty")

warn() { echo "[econark-sync] $*" >&2; [ "$STRICT" = "1" ] && RC=1; return 0; }
note() { echo "[econark-sync] $*"; }

[ -f "$ALLOW" ] || { warn "no allowlist at $ALLOW; nothing to do"; exit $RC; }

# --- locate an econ-ark-tools checkout -------------------------------------------------------
CLONE=""
for c in "${ECONARK_TOOLS_REPO:-}" \
         "$ROOT/../../econ-ark/econ-ark-tools" \
         "/home/shared/github/econ-ark/econ-ark-tools" \
         "$HOME/GitHub/econ-ark/econ-ark-tools"; do
  [ -n "$c" ] && [ -d "$c/.git" ] && { CLONE=$(cd "$c" && pwd); break; }
done

# --- refresh origin/master, rate-limited, best effort ----------------------------------------
MAXAGE="${ECONARK_SYNC_MAXAGE:-3600}"
if [ -n "$CLONE" ] && [ "${ECONARK_SYNC_REMOTE:-1}" != "0" ]; then
  age=$(( $(date +%s) - $( [ -f "$STAMP" ] && stat -c %Y "$STAMP" 2>/dev/null || stat -f %m "$STAMP" 2>/dev/null || echo 0 ) ))
  if [ "$MAXAGE" = "0" ] || [ "$age" -ge "$MAXAGE" ]; then
    if timeout 20 git -C "$CLONE" fetch --quiet origin master 2>/dev/null; then
      touch "$STAMP"; note "fetched origin/master into $CLONE"
    else
      note "fetch failed or offline; using the checkout as-is"
    fi
  fi
fi

# --- fetch one path's upstream bytes to stdout ------------------------------------------------
upstream() {   # $1 = repo-relative path
  local p="$1"
  if [ -n "$CLONE" ]; then
    git -C "$CLONE" show "origin/master:$p" 2>/dev/null && return 0
    git -C "$CLONE" show "HEAD:$p"          2>/dev/null && return 0   # detached / no origin ref
    [ -f "$CLONE/$p" ] && cat "$CLONE/$p"   && return 0
  fi
  [ "${ECONARK_SYNC_REMOTE:-1}" = "0" ] && return 1
  command -v curl >/dev/null 2>&1 || return 1
  curl -fsSL --max-time 20 "$RAW/$p" 2>/dev/null
}

changed=0 checked=0
while IFS= read -r path; do
  path="${path%%#*}"; path="$(echo "$path" | xargs)"      # strip comments + whitespace
  [ -z "$path" ] && continue
  for p in "${PROTECTED[@]}"; do
    [ "$path" = "$p" ] && { warn "REFUSED $path -- on the PROTECTED list (carries a local fix)"; continue 2; }
  done
  dest="$ROOT/$path"
  [ -f "$dest" ] || { warn "skipping $path -- not present locally"; continue; }
  checked=$((checked+1))
  tmp=$(mktemp) || { warn "mktemp failed"; continue; }
  if ! upstream "$path" > "$tmp" || [ ! -s "$tmp" ]; then
    warn "could not retrieve $path upstream; leaving the local copy alone"; rm -f "$tmp"; continue
  fi
  if cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"
  else
    cp "$tmp" "$dest" && rm -f "$tmp" && changed=$((changed+1)) \
      && note "UPDATED $path ($(wc -l < "$dest") lines) -- review and commit"
  fi
done < "$ALLOW"

note "checked $checked file(s), updated $changed"
exit $RC
