#!/usr/bin/env bash
# BC5 exp 0420: the shared ~/bc5-work/lean-session.sh with one critical section (a proposal: run it only on the
# maintainer's word, from the top session, not during a series, not while an emulator runs or a lean session is
# active). Codex 2026-11-15 10:37 and 15:40 UTC, LESSONS R56 second occurrence: in 189885ea the watcher could write
# its pid into a later stop's claim (a takeover between its read and its write) and released the claim between its
# retries, so a restore could start the Plasma shell during a lean play. The new file runs every read and write of
# the owner and the state and every unit start or stop under flock, checks the owner's token right before each, and
# keeps the watcher's claim through its retries (../0412-memory-guardian/lean-session.sh).
# Only this one helper changes; play-any.sh (fc7a1395) stays. The old file is kept as lean-session.sh.before-lock
# (lean-session.sh.before-race, from the first race fix, stays as it is).
#   swap-lean-lock.sh          dry: the checks (flock on the box) and the diff; changes nothing
#   swap-lean-lock.sh apply    the change; refuses while an emulator runs or a lean session is active
#   swap-lean-lock.sh undo     puts lean-session.sh.before-lock back (same refusals)
# Run on the box from a copy of this directory with ../0412-memory-guardian/lean-session.sh beside it, or with
# lean-session.sh in this directory.
set -u
W=$HOME/bc5-work; S=$W/lean-session.sh; ST=$W/lean-session.state
HERE=$(cd "$(dirname "$0")" && pwd)
NEW=$HERE/lean-session.sh; [ -f "$NEW" ] || NEW=$HERE/../0412-memory-guardian/lean-session.sh
EXPECT=189885ea # the shared helper this change is made for
md() { md5sum < "$1" | cut -c1-8; }
lean_active() { # a live owner, or a state not restored yet
  local o pid st s
  [ -s "$ST" ] && { echo "the state $ST names units not restored yet: $(tr '\n' ' ' < "$ST")"; return 0; }
  o=$(cat "$ST.owner/pid" 2> /dev/null) || return 1
  pid=${o%% *}; st=${o#* }
  s=$(cat "/proc/$pid/stat" 2> /dev/null) || return 1
  s=${s##*) }
  # shellcheck disable=SC2086
  set -- $s
  [ "${20:-}" = "$st" ] && { echo "the lean session of $pid is running"; return 0; }
  return 1
}
busy() {
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: nothing done"; return 0; }
  local why
  why=$(lean_active) && { echo "$why: nothing done"; return 0; }
  return 1
}
case "${1:-dry}" in
  dry | apply)
    [ -f "$S" ] || { echo "no $S"; exit 1; }
    [ -f "$NEW" ] && bash -n "$NEW" && grep -q 'flock -o -w' "$NEW" || { echo "no locked lean-session.sh at $NEW: nothing done"; exit 1; }
    now=$(md "$S")
    [ "$now" = "$EXPECT" ] || { echo "lean-session.sh is $now, not $EXPECT: nothing done"; exit 1; }
    command -v flock > /dev/null || { echo "flock is missing on this machine: the new helper would refuse every lean stop: nothing done"; exit 1; }
    t=$(mktemp -d "$W/.lock-check.XXXX") || exit 1
    flock -o -w 2 -E 75 "$t/l" true; rc=$?
    rm -rf "$t"
    [ "$rc" = 0 ] || { echo "flock -o -w 2 -E 75 does not work here (exit $rc): nothing done"; exit 1; }
    echo "flock: $(command -v flock) ($(flock --version 2> /dev/null | head -1)), works"
    echo "lean-session.sh now: $now; the new one: $(md "$NEW")"
    diff -u "$S" "$NEW" | head -400
    if [ "${1:-dry}" = dry ]; then echo "dry: nothing changed"; exit 0; fi
    busy && exit 1
    [ -e "$S.before-lock" ] || cp -p "$S" "$S.before-lock" || exit 1
    [ "$(md "$S.before-lock")" = "$EXPECT" ] || { echo "$S.before-lock is not $EXPECT: nothing done"; exit 1; }
    cp "$NEW" "$S.lock-new" && chmod 755 "$S.lock-new" && mv -fT "$S.lock-new" "$S" || { rm -f "$S.lock-new"; echo "could not put the new file in place: nothing done"; exit 1; }
    echo "applied: lean-session.sh $(md "$S"); the old one is $S.before-lock ($(md "$S.before-lock")); undo: bash $0 undo" ;;
  undo)
    [ -f "$S.before-lock" ] || { echo "no $S.before-lock: nothing to undo"; exit 1; }
    busy && exit 1
    cp -p "$S.before-lock" "$S.lock-undo" && mv -fT "$S.lock-undo" "$S" || { rm -f "$S.lock-undo"; exit 1; }
    rm -f "$ST.lock" "$ST.lock.d"
    echo "undone: lean-session.sh $(md "$S")" ;;
  *) echo "usage: swap-lean-lock.sh [dry | apply | undo]"; exit 1 ;;
esac
