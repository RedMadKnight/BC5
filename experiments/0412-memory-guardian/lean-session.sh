#!/usr/bin/env bash
# BC5: the lean session for a play, shared (~/bc5-work/lean-session.sh; exp 0412 README section 96; from lean0412.sh of
# 2026-11-11, README section 30; the maintainer's "tak" of 2026-11-14 to "the lean shortcut stops the Plasma shell for
# the time of a play"). Called by play-any.sh when BC5_LEAN=1. No root.
# While the emulator runs, the parts of the desktop that hold memory and GPU buffers and are not needed in a game are
# stopped: plasma-plasmashell.service (the panel, the desktop and the notifications: about 170 MiB of memory and
# 174 MiB of GPU memory, README section 18). KWin, PipeWire, the pad's path, sshd and tailscale are not touched.
# Everything stopped is started again when the launcher's process is gone, whatever ended it: a watcher of its own
# (setsid, outside the launcher's process group) waits for that and runs the restore, so a normal exit, the hard
# stop, a crash and a kill of the launcher all end the same way. The state is in <state file>.
#   lean-session.sh dry                    what would be stopped, with its memory now; stops nothing
#   lean-session.sh stop <launcher pid>    claim the session, stop the units that are active, note them, start the
#                                          watcher; exit 3 and change nothing when another live process owns it
#   lean-session.sh restore [owner pid]    start the noted units again (the watcher runs this; safe to run by hand,
#                                          twice); then the claim goes if its owner is gone or is the pid given
#   lean-session.sh watch <launcher pid>   (internal) wait until the pid is gone, take the claim, then restore
# One owner (2026-11-15, Codex's entry of 10:07 UTC in codex-to-claude.md; LESSONS R56): a second lean click while a
# session ran used to replace the state with the units active right then (none: the shell was stopped already), so the
# first session's watcher restored nothing and the Plasma shell did not come back. Now the session has one owner, the
# directory <state>.owner holding "pid starttime", made by an atomic rename (rename never replaces a directory that is
# not empty), so of two stops at once one wins. A stop while the owner lives changes nothing and exits 3. An owner
# whose process is gone (or whose pid now belongs to another process: the start time differs) is taken over, and the
# units it noted are kept: the new state is the old one plus what is active now. When the launcher is gone its watcher
# takes the claim for the restore (a stop in that time is refused), and the restore releases it.
set -u
E=$HOME/bc5-work; STATE=$E/lean-session.state; LOG=$E/lean-session.log; OWN=$STATE.owner
UNITS="plasma-plasmashell.service"
say() { printf '%s lean: %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
# The start time of a process (field 22 of /proc/<pid>/stat), empty when it is gone.
started() {
  local s
  s=$(cat "/proc/$1/stat" 2> /dev/null) || return 0
  s=${s##*) }
  # shellcheck disable=SC2086
  set -- $s
  echo "${20:-}"
}
# "pid starttime" of the owner, empty when there is none.
owner() { cat "$OWN/pid" 2> /dev/null; }
alive() { [ -n "${1:-}" ] && [ -d "/proc/$1" ] && [ "$(started "$1")" = "${2:-}" ]; }
# Claim the session for pid $1: 0 claimed, 3 a live owner has it, 1 failed.
claim() {
  local me=$1 tmp=$E/.lean-session.claim.$$ st=$E/.lean-session.stale.$$ o s _
  rm -rf "$tmp" "$st"
  mkdir -p "$tmp" && echo "$me $(started "$me")" > "$tmp/pid" || return 1
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if mv -T "$tmp" "$OWN" 2> /dev/null; then return 0; fi
    o=$(owner)
    if [ -z "$o" ]; then sleep 0.2; continue; fi # it is being moved or written: look again
    # shellcheck disable=SC2086
    if alive $o; then
      rm -rf "$tmp"; say "the lean session of ${o%% *} is running: nothing changed for $me"; return 3
    fi
    if mv -T "$OWN" "$st" 2> /dev/null; then
      # the claim may have passed to a live watcher between the look and the move: then it goes back
      s=$(cat "$st/pid" 2> /dev/null)
      # shellcheck disable=SC2086
      if [ "$s" != "$o" ] && alive $s; then mv -T "$st" "$OWN" 2> /dev/null; continue; fi
      rm -rf "$st"; say "the owner ${o%% *} is gone: $me takes the session over (the units it noted are kept)"
    fi
  done
  rm -rf "$tmp"; say "could not claim the session for $me"; return 1
}
# The claim goes when its owner is gone or is the pid given.
release() {
  local o
  o=$(owner)
  # shellcheck disable=SC2086
  if [ -n "$o" ] && { [ "${o%% *}" = "${1:-}" ] || ! alive $o; }; then rm -rf "$OWN"; fi
}
case "${1:-}" in
  dry)
    for u in $UNITS; do
      echo "dry: would stop $u (now $(systemctl --user is-active "$u" 2>&1), memory $(( $(systemctl --user show -p MemoryCurrent --value "$u" 2> /dev/null | grep -E '^[0-9]+$' || echo 0) / 1048576 )) MiB) and start it again when the launcher is gone"
    done
    echo "dry: nothing stopped" ;;
  stop)
    PID=${2:?the launcher pid}
    mkdir -p "$E" || exit 1
    claim "$PID"; rc=$?
    [ "$rc" = 0 ] || exit "$rc"
    # The owner alone writes the state; what an earlier session noted and could not start again stays in it.
    { cat "$STATE" 2> /dev/null
      for u in $UNITS; do
        if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then echo "$u"; fi
      done; } | awk 'NF && !seen[$0]++' > "$STATE.new" || exit 1
    mv -fT "$STATE.new" "$STATE" || exit 1
    # The watcher first: if stopping fails half way, the restore still comes.
    (setsid nohup /usr/bin/bash "$0" watch "$PID" > /dev/null 2>&1 < /dev/null &)
    while read -r u; do
      [ -n "$u" ] || continue
      if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then
        if systemctl --user stop "$u"; then say "stopped $u"; else say "could not stop $u"; fi
      fi
    done < "$STATE" ;;
  restore)
    [ -s "$STATE" ] || { say "nothing to restore"; release "${2:-}"; exit 0; }
    # A unit that could not be started stays in the state file, so that a later restore tries it again (2026-11-15,
    # Codex's review: the file used to go to .done whatever happened, and the next restore said "nothing to restore").
    : > "$STATE.left" || exit 1
    while read -r u; do
      [ -n "$u" ] || continue
      if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then say "$u is active already"; else
        if systemctl --user start "$u"; then say "started $u"; else say "COULD NOT START $u (kept for the next restore; by hand: systemctl --user start $u)"; echo "$u" >> "$STATE.left"; fi
      fi
    done < "$STATE"
    if [ -s "$STATE.left" ]; then mv -fT "$STATE.left" "$STATE"; release "${2:-}"; exit 1; fi
    rm -f "$STATE.left"; mv -fT "$STATE" "$STATE.done"; release "${2:-}" ;;
  watch)
    PID=${2:?the launcher pid}
    while [ -d "/proc/$PID" ]; do sleep 1; done
    # The claim passes from the launcher to this watcher for the restore. When it is not the launcher's any more, a
    # later stop took the session over with its state, and that stop's own watcher restores.
    o=$(owner)
    [ "${o%% *}" = "$PID" ] || { say "the session of $PID was taken over (owner: ${o:-none}): this watcher ends"; exit 0; }
    if ! { printf '%s %s\n' "$$" "$(started $$)" > "$OWN/.pid.$$" && mv -f "$OWN/.pid.$$" "$OWN/pid"; } 2> /dev/null; then
      rm -f "$OWN/.pid.$$" 2> /dev/null; say "the session of $PID was taken over: this watcher ends"; exit 0
    fi
    o=$(owner)
    [ "${o%% *}" = "$$" ] || { say "the session of $PID was taken over (owner: ${o:-none}): this watcher ends"; exit 0; }
    for _ in 1 2 3 4 5 6; do /usr/bin/bash "$0" restore "$$" && exit 0; sleep "${LEAN_RETRY_S:-5}"; done   # a failed start is tried again
    say "the watcher gives up after six tries; the state file keeps what is left"; release "$$"; exit 1 ;;
  *) echo "usage: lean-session.sh dry | stop <launcher pid> | restore [owner pid]"; exit 1 ;;
esac
