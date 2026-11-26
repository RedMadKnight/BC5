#!/usr/bin/env bash
# BC5 experiment 0367 (exp 0360's build0360.sh): one private emulator per variant, ~/bc5-work/exp0367/<variant>/kyty_emulator.
# The shared host tree's src/libs/bc5LleAgc.cpp, src/loader/runtimeLinker.cpp and src/kernel/pthread.cpp are copied with
# their sibling includes into a PRIVATE source tree and the given perl patches applied there; with FULL_STATE=<file
# beside this script> a private copy of the backend's src/full_state.cpp (candidate C1) is compiled with the shared
# backend archive's own compile command (~/bc5-work/backend-ubuntu/compile_commands.json, -Werror and all) into a private
# object that the link takes in front of the archive. The changed host units are compiled with the shared normal build's
# compdb commands; the shared link command runs with the private objects. ~/src/KytyPlus, ~/src/bc5, the shared builds
# and the archive are only read.
# usage: [FULL_STATE=full_state-0367.cpp] build0367.sh <variant> <patch.pl>...   (on the box; CPU only, nice 19)
set -u
VAR=${1:?a variant name}; shift
case "$VAR" in *[!a-z0-9]* | "") echo "the variant is lower-case letters and digits"; exit 1 ;; esac
[ $# -ge 1 ] || { echo "at least one patch"; exit 1; }
E=$HOME/bc5-work/exp0367; V=$E/$VAR; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a; BB=$HOME/bc5-work/backend-ubuntu
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-1000ad2a}; EXPECT_FS=${EXPECT_FS:-29f7dd6d}
UNITS="src/libs/bc5LleAgc.cpp src/loader/runtimeLinker.cpp src/kernel/pthread.cpp"
want_md5() { case "$1" in src/libs/bc5LleAgc.cpp) echo "${EXPECT_AGC:-e7cc2f60}" ;; src/loader/runtimeLinker.cpp) echo "${EXPECT_RTL:-96e03695}" ;; src/kernel/pthread.cpp) echo "${EXPECT_PT:-46c7ac3a}" ;; esac; }
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$V/src; FS=${FULL_STATE:-}
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^exp 0367 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
for u in $UNITS; do [ "$(m "$TREE/$u")" = "$(want_md5 "$u")" ] || { echo "$u is $(m "$TREE/$u"), not $(want_md5 "$u"): stop"; exit 1; }; done
if [ -n "$FS" ]; then
  [ -f "$HERE/$FS" ] || { echo "no $FS beside this script"; exit 1; }
  [ "$(m "$HOME/src/bc5/backend/src/full_state.cpp")" = "$EXPECT_FS" ] || { echo "~/src/bc5/backend/src/full_state.cpp is $(m "$HOME/src/bc5/backend/src/full_state.cpp"), not main's $EXPECT_FS: stop"; exit 1; }
  grep -q '"file": "[^"]*/backend/src/full_state.cpp"' "$BB/compile_commands.json" || { echo "no full_state.cpp in $BB/compile_commands.json"; exit 1; }
fi
[ -f "$HERE/build0367.py" ] || { echo "no build0367.py beside this script"; exit 1; }
for p in "$@"; do [ -f "$HERE/$p" ] || { echo "no $p beside this script"; exit 1; }; done
mkdir -p "$V"
echo "exp 0367 | build of ~/bc5-work/exp0367/$VAR/kyty_emulator ($*${FS:+ + backend $FS}; private copies compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0367 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$V/obj"; mkdir -p "$V/obj"
for u in $UNITS; do
  d=$(dirname "$u"); mkdir -p "$SRC/$d"
  cp "$TREE/$u" "$SRC/$u" || exit 1
  for f in "$TREE"/"$d"/*.inc "$TREE"/"$d"/*.h; do [ -e "$f" ] && cp "$f" "$SRC/$d/"; done  # the unit's sibling includes
done
: > "$V/patch.out"
for p in "$@"; do perl "$HERE/$p" "$SRC" >> "$V/patch.out" 2>&1 || { echo "patch $p failed:"; cat "$V/patch.out"; exit 1; }; done
cat "$V/patch.out"
CHANGED=""
for u in $UNITS; do
  if ! cmp -s "$TREE/$u" "$SRC/$u"; then
    CHANGED="$CHANGED $u"
    diff -u "$TREE/$u" "$SRC/$u" > "$V/$(basename "$u")-0367.diff"
    echo "$u: $(grep -c '^[-+][^-+]' "$V/$(basename "$u")-0367.diff") lines changed"
  fi
done
EXTRA=""
if [ -n "$FS" ]; then
  cp "$HERE/$FS" "$V/full_state.cpp" || exit 1
  diff -u "$HOME/src/bc5/backend/src/full_state.cpp" "$V/full_state.cpp" > "$V/full_state.cpp-0367.diff"
  echo "backend full_state.cpp: $(grep -c '^[-+][^-+]' "$V/full_state.cpp-0367.diff") lines changed against ~/src/bc5's $(m "$HOME/src/bc5/backend/src/full_state.cpp")"
  CMD=$(sed -n 's/^ *"command": "\(.*\/backend\/src\/full_state.cpp\)",*$/\1/p' "$BB/compile_commands.json" | head -1)
  [ -n "$CMD" ] || { echo "no compile command for full_state.cpp"; exit 1; }
  CMD=$(printf '%s' "$CMD" | sed "s#-o [^ ]*full_state.cpp.o#-o $V/obj/full_state.cpp.o#; s#-c [^ ]*/backend/src/full_state.cpp#-c $V/full_state.cpp#")
  case "$CMD" in *"-o $V/obj/full_state.cpp.o"*"-c $V/full_state.cpp"*) ;; *) echo "the rewritten compile command does not name the private files: $CMD"; exit 1 ;; esac
  echo "== $(date +%T) backend full_state.cpp: $CMD" | cut -c1-300
  distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 $CMD" > "$V/full_state.out" 2>&1 || { echo "the backend unit failed to compile:"; cat "$V/full_state.out"; exit 1; }
  EXTRA="+$V/obj/full_state.cpp.o"
fi
[ -n "$CHANGED$EXTRA" ] || { echo "nothing changed"; exit 1; }
{ echo "shared binary md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH"); units:"; for u in $UNITS; do echo "  $u $(m "$TREE/$u")"; done; echo "changed:$CHANGED"; [ -n "$FS" ] && echo "backend: $FS $(m "$HERE/$FS") over ~/src/bc5 full_state.cpp $(m "$HOME/src/bc5/backend/src/full_state.cpp")"; echo "patches:"; for p in "$@"; do echo "  $p $(m "$HERE/$p")"; done; } > "$V/build-inputs.txt"; cat "$V/build-inputs.txt"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$V/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$V/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
# shellcheck disable=SC2086
distrobox enter ubuntu -- python3 -I "$HERE/build0367.py" "$E/compdb.json" "$SRC" "$V/obj" "$B" "$BIN" $CHANGED $EXTRA > "$V/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$V/build.out"), warnings $(grep -c 'warning:' "$V/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED\|multiple definition" "$V/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $V/build.out"; exit 1; }
m "$BIN" > "$V/binary.md5"; echo "md5 $(cat "$V/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$V/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: cpu meter $(strings "$BIN" | grep -c 'cpu meter:'), cpu prof $(strings "$BIN" | grep -c 'cpu prof:'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $VAR $(cat "$V/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with$CHANGED of $*${FS:+ + backend $FS} + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$E/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); ~/src/bc5 full_state.cpp after: $(m "$HOME/src/bc5/backend/src/full_state.cpp")"
