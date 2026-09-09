#!/bin/bash
# phase_alert.sh v2 — phase-boundary attention alert with ACKNOWLEDGMENT
# (owner protocol 2026-08-07, amended same day: "when I click on the
# dialog box to acknowledge the alert... kill further alerts and warn me
# that unless I tell you not to, you're going to start the next phase in
# 10 min").
#
# Usage: phase_alert.sh "message" [reps=5] [interval_s=120]
#
# Channels per repeat: speaker sound x3 (PipeWire), terminal bell to
# every pts, GNOME critical banner, tmux status message, and ONE zenity
# dialog per repeat (timeout just under the interval, so at most one is
# on screen). The dialog is the ACK channel: clicking OK — or closing
# the window — means the owner is at the machine.
#
# stdout contract (the caller watches via Monitor):
#   "PHASE_ALERT_ACKED"   — owner clicked; remaining repeats killed.
#                           Caller: warn the owner that the next phase
#                           starts in ~10 min unless they say otherwise,
#                           then proceed after that grace.
#   "PHASE_ALERT_TIMEOUT" — no interaction through all repeats.
#                           Caller: proceed immediately (the ~10 min of
#                           alerts WAS the grace).
MSG="${1:-Claude: phase boundary}"; REPS="${2:-5}"; INT="${3:-120}"
ACK="$(mktemp -u /tmp/phase_alert_ack.XXXXXX)"
U="/run/user/$(id -u)"
export XDG_RUNTIME_DIR="$U" DBUS_SESSION_BUS_ADDRESS="unix:path=$U/bus"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" DISPLAY="${DISPLAY:-:0}"
SOUND=/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
DTO=$(( INT > 10 ? INT - 5 : 55 ))
for i in $(seq 1 "$REPS"); do
  [ -f "$ACK" ] && break
  (for _ in 1 2 3; do
     pw-play "$SOUND" 2>/dev/null \
       || aplay -q /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null
   done) &
  for t in /dev/pts/[0-9]*; do
    [ -w "$t" ] && printf '\a' > "$t" 2>/dev/null
  done
  notify-send --urgency=critical --app-name="HAFiscal lab" "⏰ ${MSG}" \
    "repeat ${i}/${REPS} — click the dialog's OK to acknowledge (stops the alerts; Claude then gives you ~10 min before proceeding)" 2>/dev/null
  for s in /tmp/tmux-$(id -u)/*; do
    tmux -S "$s" display-message -d 10000 "⏰ ${MSG} (${i}/${REPS})" 2>/dev/null
  done
  ( zenity --warning --title="HAFiscal lab — attention (${i}/${REPS})" \
      --text="${MSG}\n\nClick OK to acknowledge — the alerts stop and Claude will give you ~10 min to redirect before it proceeds." \
      --timeout="$DTO" 2>/dev/null
    rc=$?
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then touch "$ACK"; fi
  ) &
  if [ "$i" -lt "$REPS" ]; then
    for _ in $(seq 1 $((INT / 5))); do
      [ -f "$ACK" ] && break
      sleep 5
    done
  fi
done
# let the final repeat's dialog live out its timeout before the verdict
while pgrep -P $$ zenity >/dev/null 2>&1; do
  [ -f "$ACK" ] && break
  sleep 5
done
sleep 1
if [ -f "$ACK" ]; then
  rm -f "$ACK"
  pkill -P $$ zenity 2>/dev/null
  echo "PHASE_ALERT_ACKED"
else
  echo "PHASE_ALERT_TIMEOUT"
fi
