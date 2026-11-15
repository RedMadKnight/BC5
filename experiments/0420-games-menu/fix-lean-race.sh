#!/usr/bin/env bash
# BC5 exp 0420: the lean session's race fixed in the SHARED launcher (a proposal: run it only on the maintainer's word,
# not during a series and not while a lean session is active). Codex 2026-11-15 10:07 UTC, LESSONS R56: the shared
# ~/bc5-work/play-any.sh (92c090c5) calls `lean-session.sh stop $$` before its pgrep check, and the shared
# lean-session.sh replaces its state with the units active right then, so a second lean click during a lean play
# wrote an empty state and the first play's watcher restored nothing (the Plasma shell did not come back).
# The change: the three lean lines move after the launcher's refusing checks (pgrep, the emulator, the settings file),
# a stop that finds a live lean session (exit 3) refuses the start, and lean-session.sh is the one-owner version
# (../0412-memory-guardian/lean-session.sh). Both old files are kept as *.before-race.
#   fix-lean-race.sh            dry: the diff it would make, the checks; changes nothing
#   fix-lean-race.sh apply      the change; refuses while an emulator runs or a lean session is active
#   fix-lean-race.sh undo       puts both *.before-race files back
#   fix-lean-race.sh make <f>   (tests) the changed launcher for the file f on stdout
# Run on the box, from a copy of this experiment's directory with ../0412-memory-guardian/lean-session.sh beside it,
# or with lean-session.sh in this directory.
set -u
W=$HOME/bc5-work; P=$W/play-any.sh; S=$W/lean-session.sh; ST=$W/lean-session.state
HERE=$(cd "$(dirname "$0")" && pwd)
NEW_LS=$HERE/lean-session.sh; [ -f "$NEW_LS" ] || NEW_LS=$HERE/../0412-memory-guardian/lean-session.sh
EXPECT=92c090c5 # the shared launcher this change is made for
OLD1='# exp 0412 (2026-11-14, the maintainer: the lean shortcut stops the Plasma shell for the play): lean-session.sh stops'
OLD2='# plasma-plasmashell.service now and starts it again when this launcher is gone, whatever ended it.'
OLD3='if [ "${BC5_LEAN:-0}" = 1 ] && [ -x "$HOME/bc5-work/lean-session.sh" ]; then /usr/bin/bash "$HOME/bc5-work/lean-session.sh" stop $$; fi'
AFTER='mkdir -p "$KYTY_BC5_MENU_DIR"'
make() { # the changed launcher on stdout; 1 when a line it needs is not there exactly once
  local n
  for l in "$OLD1" "$OLD2" "$OLD3" "$AFTER"; do
    n=$(grep -cxF -- "$l" "$1"); [ "$n" = 1 ] || { echo "fix-lean-race: a line is there $n times, not once: $l" >&2; return 1; }
  done
  awk -v o1="$OLD1" -v o2="$OLD2" -v o3="$OLD3" -v a="$AFTER" '
    $0 == o1 || $0 == o2 || $0 == o3 { next }
    { print }
    $0 == a {
      print o1
      print "# plasma-plasmashell.service now and starts it again when this launcher is gone, whatever ended it. It comes after"
      print "# every check that can refuse the start (2026-11-15, Codex 10:07 UTC, LESSONS R56: a second click used to stop the"
      print "# shell and rewrite the state before pgrep refused it); a stop that finds a live lean session (exit 3) refuses too."
      print "if [ \"${BC5_LEAN:-0}\" = 1 ] && [ -x \"$HOME/bc5-work/lean-session.sh\" ]; then"
      print "  /usr/bin/bash \"$HOME/bc5-work/lean-session.sh\" stop $$"
      print "  [ $? = 3 ] && { say \"A lean session is already running.\"; exit 1; }"
      print "fi"
    }' "$1"
}
# A lean session is active: a live owner (the new lean-session.sh) or a state not restored yet (either version).
lean_active() {
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
case "${1:-dry}" in
  make) make "${2:?a launcher}" ;;
  dry | apply)
    [ -f "$P" ] || { echo "no $P"; exit 1; }
    [ -f "$NEW_LS" ] && bash -n "$NEW_LS" && grep -q 'lean-session.state.owner\|STATE.owner' "$NEW_LS" || { echo "no one-owner lean-session.sh at $NEW_LS: nothing done"; exit 1; }
    now=$(md5sum < "$P" | cut -c1-8)
    [ "$now" = "$EXPECT" ] || { echo "play-any.sh is $now, not $EXPECT: nothing done"; exit 1; }
    make "$P" > "$P.race-new" && bash -n "$P.race-new" || { rm -f "$P.race-new"; echo "the new launcher is not made or does not parse: nothing done"; exit 1; }
    [ "$(diff "$P" "$P.race-new" | grep -c '^<')" = 3 ] && [ "$(diff "$P" "$P.race-new" | grep -c '^>')" = 8 ] || { rm -f "$P.race-new"; echo "the change is not 3 lines out and 8 in: nothing done"; exit 1; }
    echo "play-any.sh now: $now; with the change: $(md5sum < "$P.race-new" | cut -c1-8)"
    echo "lean-session.sh now: $(md5sum < "$S" 2> /dev/null | cut -c1-8); the new one: $(md5sum < "$NEW_LS" | cut -c1-8)"
    diff -u "$P" "$P.race-new"
    if [ "${1:-dry}" = dry ]; then rm -f "$P.race-new"; echo "dry: nothing changed"; exit 0; fi
    pgrep -x kyty_emulator > /dev/null && { rm -f "$P.race-new"; echo "an emulator runs: nothing done"; exit 1; }
    why=$(lean_active) && { rm -f "$P.race-new"; echo "$why: nothing done"; exit 1; }
    [ -e "$P.before-race" ] || cp -p "$P" "$P.before-race" || { rm -f "$P.race-new"; exit 1; }
    [ -e "$S.before-race" ] || [ ! -e "$S" ] || cp -p "$S" "$S.before-race" || { rm -f "$P.race-new"; exit 1; }
    cp "$NEW_LS" "$S.race-new" && chmod 755 "$S.race-new" && mv -fT "$S.race-new" "$S" || { rm -f "$P.race-new" "$S.race-new"; echo "could not put lean-session.sh in place: nothing done"; exit 1; }
    chmod --reference="$P" "$P.race-new" && mv -fT "$P.race-new" "$P" &&
      echo "applied: play-any.sh $(md5sum < "$P" | cut -c1-8), lean-session.sh $(md5sum < "$S" | cut -c1-8); the old ones are $P.before-race and $S.before-race" ;;
  undo)
    [ -f "$P.before-race" ] || { echo "no $P.before-race: nothing to undo"; exit 1; }
    pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: nothing done"; exit 1; }
    why=$(lean_active) && { echo "$why: nothing done"; exit 1; }
    cp -p "$P.before-race" "$P" && { [ ! -f "$S.before-race" ] || cp -p "$S.before-race" "$S"; } &&
      echo "undone: play-any.sh $(md5sum < "$P" | cut -c1-8), lean-session.sh $(md5sum < "$S" 2> /dev/null | cut -c1-8); the .before-race files kept" ;;
  *) echo "usage: fix-lean-race.sh [dry | apply | undo | make <launcher>]"; exit 1 ;;
esac
