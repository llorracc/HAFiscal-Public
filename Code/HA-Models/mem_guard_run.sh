#!/bin/bash
# G3, plan 20260806-1211h (OOM record 20260806-0101h): run a command inside a
# systemd user scope with MemoryHigh/MemoryMax derived from MemTotal, so a
# battery overshoot degrades into throttling and then a BATTERY-scoped kill —
# never a global OOM that (by oom_score_adj ordering) eats the desktop
# session, gsd-xsettings, and with Linger=no the whole user slice.
#
# Usage:  mem_guard_run.sh <command...>
# Env:    HAFISCAL_MEMGUARD=off           disable (exec the command plain)
#         HAFISCAL_MEMGUARD_HIGH_PCT=78   MemoryHigh as % of MemTotal
#         HAFISCAL_MEMGUARD_MAX_PCT=85    MemoryMax  as % of MemTotal
# Fail-soft: no systemd-run / no user manager / no /proc/meminfo -> plain exec.
# Concurrency-only: changes no computed result.
set -u
if [ "${HAFISCAL_MEMGUARD:-on}" = "off" ] \
   || ! command -v systemd-run >/dev/null 2>&1 \
   || [ ! -r /proc/meminfo ]; then
  exec "$@"
fi
# v2 (2026-08-06 13:41 contained-OOM lesson): size from MemTotal MINUS
# Unevictable — a % of raw total still overcommits GLOBALLY on a box with a
# 9 GiB mlock pin (85% of 60.5 = 51.4, + 9.2 pin + desktop > 60.5), which is
# why the retry's OOM was global rather than scope-internal. Netting out the
# pin makes the scope cap itself guarantee global feasibility.
MT_KB=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
UNEV_KB=$(awk '/^Unevictable:/{print $2}' /proc/meminfo)
BASE_KB=$(( MT_KB - ${UNEV_KB:-0} ))
HIGH_PCT=${HAFISCAL_MEMGUARD_HIGH_PCT:-78}
MAX_PCT=${HAFISCAL_MEMGUARD_MAX_PCT:-85}
HIGH_KB=$(( BASE_KB * HIGH_PCT / 100 ))
MAX_KB=$(( BASE_KB * MAX_PCT / 100 ))
# Probe that the user manager accepts scopes (headless/cron sessions may not).
if systemd-run --user --scope --collect -q -p MemoryMax=infinity true \
     >/dev/null 2>&1; then
  echo "[mem-guard] scope: MemoryHigh=$((HIGH_KB/1024/1024))G" \
       "MemoryMax=$((MAX_KB/1024/1024))G (of $((MT_KB/1024/1024))G total)" >&2
  exec systemd-run --user --scope --collect -q \
    -p "MemoryHigh=${HIGH_KB}K" -p "MemoryMax=${MAX_KB}K" -- "$@"
fi
echo "[mem-guard] systemd user manager unavailable; running unguarded" >&2
exec "$@"
