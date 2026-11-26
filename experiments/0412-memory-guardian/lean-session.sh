#!/usr/bin/env bash
# BC5: the lean session for a play, shared (~/bc5-work/lean-session.sh; exp 0412 README section 96; from lean0412.sh of
# 2026-11-11, README section 30; the maintainer's yes of 2026-11-14 to "the lean shortcut stops the Plasma shell for
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
#                                          twice); exit 3 and change nothing while another live process owns the
#                                          session (a lean play runs); the claim goes when the restore succeeds
#   lean-session.sh watch <pid> <start>    (internal) wait until that launcher is gone, take the claim, restore
# One owner (2026-11-15, Codex's entry of 10:07 UTC in codex-to-claude.md; LESSONS R56): a second lean click while a
# session ran used to replace the state with the units active right then. The session has one owner, the token
# "pid starttime" (field 22 of /proc/<pid>/stat, so a reused pid is not taken for the owner) in <state>.owner/pid.
# One critical section (2026-11-15, Codex's entries of 10:37 and 15:40 UTC; LESSONS R56, second occurrence; R35/R36):
# every read of the owner, every write of the owner or the state and every start or stop of a unit runs under one
# lock (flock on <state>.lock), and the owner's token is checked again right before each of them. The watcher keeps
# the claim through its retries (it lives, so a stop meanwhile is refused) and releases it only after a successful
# restore or when it gives up. Without flock there is no lean session (stop exits 1, the play runs with the
# desktop); a restore still runs, unlocked, so the shell always comes back.
# Tests: LEAN_TEST_BARRIER=<dir> makes each named point wait for <dir>/<point>.go (it writes <point>.reached first);
# test-lean-session.sh (exp 0412) and test-lean-race.sh (exp 0420) force every interleaving with it, on stand-ins.
set -u
E=$HOME/bc5-work; STATE=$E/lean-session.state; LOG=$E/lean-session.log; OWN=$STATE.owner; LOCK=$STATE.lock
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
token() { echo "$1 $(started "$1")"; }
# "pid starttime" of the owner, empty when there is none.
owner() { cat "$OWN/pid" 2> /dev/null; }
alive() { [ -n "${1:-}" ] && [ -n "${2:-}" ] && [ -d "/proc/$1" ] && [ "$(started "$1")" = "$2" ]; }
# A live owner other than the token $1 (may be empty): 0 when there is one.
other_owner() {
  local o
  o=$(owner)
  # shellcheck disable=SC2086
  [ -n "$o" ] && [ "$o" != "${1:-}" ] && alive $o
}
set_owner() { mkdir -p "$OWN" && printf '%s\n' "$1" > "$OWN/.pid.$$" && mv -f "$OWN/.pid.$$" "$OWN/pid"; }
barrier() {
  local d=${LEAN_TEST_BARRIER:-} i=0
  [ -n "$d" ] || return 0
  : > "$d/$1.reached"
  while [ ! -e "$d/$1.go" ] && [ "$i" -lt 300 ]; do sleep 0.1; i=$((i + 1)); done
}
# Run this script's own step "$@" holding the lock (-o: the step's children, the watcher among them, never hold it).
# 75: the lock was not had in time.
locked() { flock -o -w "${LEAN_LOCK_S:-60}" -E 75 "$LOCK" /usr/bin/bash "$0" _locked "$@"; }
have_flock() { command -v flock > /dev/null 2>&1; }

# The steps below run only inside locked() (or, for a restore without flock, alone).
step_stop() { # <launcher token>
  local me=$1 o
  o=$(owner)
  if other_owner "$me"; then say "the lean session of ${o%% *} is running: nothing changed for ${me%% *}"; return 3; fi
  # shellcheck disable=SC2086
  alive $me || { say "the launcher ${me%% *} is gone: no lean session"; return 1; }
  [ -n "$o" ] && [ "$o" != "$me" ] && say "the owner ${o%% *} is gone: ${me%% *} takes the session over (the units it noted are kept)"
  set_owner "$me" || return 1
  # The owner alone writes the state; what an earlier session noted and could not start again stays in it.
  [ "$(owner)" = "$me" ] || return 1
  { cat "$STATE" 2> /dev/null
    for u in $UNITS; do
      if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then echo "$u"; fi
    done; } | awk 'NF && !seen[$0]++' > "$STATE.new" || return 1
  [ "$(owner)" = "$me" ] || { rm -f "$STATE.new"; return 1; }
  mv -fT "$STATE.new" "$STATE" || return 1
  # The watcher first: if stopping fails half way, the restore still comes.
  # shellcheck disable=SC2086
  (setsid nohup /usr/bin/bash "$0" watch $me > /dev/null 2>&1 < /dev/null &)
  while read -r u; do
    [ -n "$u" ] || continue
    [ "$(owner)" = "$me" ] || { say "the claim of ${me%% *} is gone: no more stops"; return 1; }
    if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then
      if systemctl --user stop "$u"; then say "stopped $u"; else say "could not stop $u"; fi
    fi
  done < "$STATE"
  return 0
}
step_restore() { # [caller token]: 0 done, 1 a start failed (the state keeps it), 3 another live owner has the session
  local me=${1:-} o
  o=$(owner)
  if other_owner "$me"; then say "the lean session of ${o%% *} is running: no restore now"; return 3; fi
  if [ ! -s "$STATE" ]; then
    say "nothing to restore"
    # shellcheck disable=SC2086
    if [ -n "$o" ] && { [ "$o" = "$me" ] || ! alive $o; }; then rm -rf "$OWN"; fi
    return 0
  fi
  # A unit that could not be started stays in the state file, so that a later restore tries it again (2026-11-15,
  # Codex's review: the file used to go to .done whatever happened, and the next restore said "nothing to restore").
  : > "$STATE.left" || return 1
  while read -r u; do
    [ -n "$u" ] || continue
    if other_owner "$me"; then echo "$u" >> "$STATE.left"; continue; fi   # the token again, right before the start
    if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then say "$u is active already"; else
      if systemctl --user start "$u"; then say "started $u"; else say "COULD NOT START $u (kept for the next restore; by hand: systemctl --user start $u)"; echo "$u" >> "$STATE.left"; fi
    fi
  done < "$STATE"
  if other_owner "$me"; then rm -f "$STATE.left"; return 3; fi
  if [ -s "$STATE.left" ]; then mv -fT "$STATE.left" "$STATE"; return 1; fi   # the claim stays with its owner
  rm -f "$STATE.left"; mv -fT "$STATE" "$STATE.done"
  o=$(owner)
  # shellcheck disable=SC2086
  if [ -n "$o" ] && { [ "$o" = "$me" ] || ! alive $o; }; then rm -rf "$OWN"; fi
  return 0
}
step_handover() { # <launcher token> <watcher token>: 0 the watcher owns it now, 4 it was taken over
  barrier handover-locked
  [ "$(owner)" = "$1" ] || { say "the session of ${1%% *} was taken over (owner: $(owner || true)): this watcher ends"; return 4; }
  set_owner "$2" && [ "$(owner)" = "$2" ]
}
step_release() { # <token>
  [ "$(owner)" = "$1" ] && rm -rf "$OWN"
  return 0
}

case "${1:-}" in
  dry)
    for u in $UNITS; do
      echo "dry: would stop $u (now $(systemctl --user is-active "$u" 2>&1), memory $(( $(systemctl --user show -p MemoryCurrent --value "$u" 2> /dev/null | grep -E '^[0-9]+$' || echo 0) / 1048576 )) MiB) and start it again when the launcher is gone"
    done
    have_flock || echo "dry: flock is missing: stop would refuse (no lean session)"
    echo "dry: nothing stopped" ;;
  stop)
    PID=${2:?the launcher pid}
    mkdir -p "$E" || exit 1
    have_flock || { say "flock is missing: no lean session for $PID"; exit 1; }
    barrier stop-before-lock
    locked stop "$(token "$PID")"; rc=$?
    [ "$rc" = 75 ] && { say "the lock was busy: no lean session for $PID"; exit 1; }
    exit "$rc" ;;
  restore)
    me=""; [ -n "${2:-}" ] && me=$(token "$2")
    if have_flock; then locked restore "$me"; rc=$?; [ "$rc" = 75 ] && say "the lock was busy: no restore"; exit "$rc"; fi
    say "flock is missing: the restore runs unlocked"; step_restore "$me"; exit $? ;;
  watch)
    PID=${2:?the launcher pid}; START=${3:-}
    while alive "$PID" "$START"; do sleep 1; done
    barrier watch-gone
    have_flock || { say "flock is missing: the watcher restores unlocked"; step_restore ""; exit $?; }
    ME=$(token $$)
    locked handover "$PID $START" "$ME" || exit 0
    barrier watch-owned
    for _ in 1 2 3 4 5 6; do   # a failed start is tried again; the claim stays the watcher's meanwhile
      locked restore "$ME"; rc=$?
      [ "$rc" = 0 ] && exit 0
      [ "$rc" = 3 ] && { say "the session is not this watcher's any more: it ends"; exit 0; }
      barrier watch-retry
      sleep "${LEAN_RETRY_S:-5}"
    done
    say "the watcher gives up after six tries; the state file keeps what is left"
    locked release "$ME"; exit 1 ;;
  _locked)
    shift; step=$1; shift
    case "$step" in
      stop) step_stop "$@" ;;
      restore) step_restore "$@" ;;
      handover) step_handover "$@" ;;
      release) step_release "$@" ;;
      *) exit 2 ;;
    esac
    exit $? ;;
  *) echo "usage: lean-session.sh dry | stop <launcher pid> | restore [owner pid]"; exit 1 ;;
esac
