#!/usr/bin/env bash
# BC5 experiment 0330: the integration of arm C's lazy list (F394) into the second title's three launchers, on the
# maintainer's yes ("Zaczynaj od A", 2026-10-26). One line goes in after each launcher's env-file loop, where arm C's
# hook was:
#   export BC5_DIRECT_LAZY_NAMES="${BC5_DIRECT_LAZY_NAMES:+$BC5_DIRECT_LAZY_NAMES,}Wwise,SoundAlloc,FileSystem,UIStringAlloc"
# With today's bc5-run.env (orbis_user_malloc) that is arm C's list exactly. bc5-run.env itself is left alone, so
# ASTRO BOT's launcher (play-astro.sh) does not change. The shortcuts reach play-pkg.sh through play-any.sh, the lean
# one with BC5_LEAN=1; the lazy list is read with getenv, so the lean build takes it too.
# Guards: no emulator or launcher, an empty lock, each launcher's md5 and its anchor once. A lock line with an EXIT trap
# that clears only that line. Backups in ~/bc5-work/exp0330/integration/. After the edit: bash -n, a one-line diff, and
# the list the launcher's first lines produce (sourced in a subshell up to the new line; nothing is started). Any failed
# check puts the backups back.
# usage: int0330.sh   (on the box)
set -u
W=$HOME/bc5-work; E=$W/exp0330; I=$E/integration; R=$E/raw; LOCK=$W/BOX-LOCK
FILES="play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh"
declare -A WANT=([play-pkg.sh]=c0357628 [play-pkg-log.sh]=e1b361a1 [play-pkg-quiet.sh]=2b23073d)
ANCHOR='done < "$ENVF"'
# shellcheck disable=SC2016
LINE='export BC5_DIRECT_LAZY_NAMES="${BC5_DIRECT_LAZY_NAMES:+$BC5_DIRECT_LAZY_NAMES,}Wwise,SoundAlloc,FileSystem,UIStringAlloc"  # exp 0330 (F394): the four CPU-only heaps lazy, 242 MiB less pinned'
EXPECT=orbis_user_malloc,Wwise,SoundAlloc,FileSystem,UIStringAlloc
md5() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/play-pkg(-log|-quiet)?\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }  # a running launcher, not a command line that names one
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(sed -n 's/^BC5_DIRECT_LAZY_NAMES=//p' "$W/bc5-run.env")" = orbis_user_malloc ] || { echo "bc5-run.env's lazy list is not orbis_user_malloc: stop"; exit 1; }
for f in $FILES; do
  [ "$(md5 "$W/$f")" = "${WANT[$f]}" ] || { echo "$f is not ${WANT[$f]}: stop"; exit 1; }
  [ "$(grep -cxF -- "$ANCHOR" "$W/$f")" = 1 ] || { echo "$f: the anchor is not there once: stop"; exit 1; }
  grep -q 'exp 0330 (F394)' "$W/$f" && { echo "$f already has the line: stop"; exit 1; }
done
[ -e "$I" ] && { echo "$I exists: stop"; exit 1; }
echo "cloud exp 0330 | integration of the lazy list into play-pkg*.sh (no emulator) | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0330 | integration" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$I" "$R" || exit 1
for f in $FILES; do cp -p "$W/$f" "$I/$f.before-0330" || exit 1; done
restore() { for f in $FILES; do cat "$I/$f.before-0330" > "$W/$f"; done; echo "RESTORED: $(for f in $FILES; do printf '%s %s  ' "$f" "$(md5 "$W/$f")"; done)"; exit 1; }
for f in $FILES; do
  awk -v l="$LINE" -v a="$ANCHOR" '{print} $0 == a {print l}' "$I/$f.before-0330" > "$I/$f.new" || restore
  cat "$I/$f.new" > "$W/$f" || restore  # in place: the file keeps its inode, owner and mode
  rm -f "$I/$f.new"
  bash -n "$W/$f" || { echo "$f does not parse"; restore; }
  diff -u "$I/$f.before-0330" "$W/$f" > "$R/int-$f.diff"
  [ "$(grep -c '^+[^+]' "$R/int-$f.diff")" = 1 ] && [ "$(grep -c '^-[^-]' "$R/int-$f.diff")" = 0 ] || { echo "$f: the diff is not one added line"; restore; }
  n=$(grep -nxF -- "$ANCHOR" "$W/$f" | cut -d: -f1)
  got=$(env -i HOME="$HOME" PATH="$PATH" bash -c 'source <(sed -n "1,$2p" "$1") > /dev/null 2>&1; echo "${BC5_DIRECT_LAZY_NAMES:-}"' _ "$W/$f" "$((n + 1))")
  [ "$got" = "$EXPECT" ] || { echo "$f gives the list [$got], not [$EXPECT]"; restore; }
  echo "$f: ${WANT[$f]} -> $(md5 "$W/$f"), the line after line $n, the list $got"
done
echo "backups: $(ls "$I" | tr '\n' ' ')"
echo "undo: for f in $FILES; do cat $I/\$f.before-0330 > $W/\$f; done"
