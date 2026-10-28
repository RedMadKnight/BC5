#!/usr/bin/env bash
# BC5 experiment 0360 (exp 0358's build0358v5.sh): one private emulator per variant, ~/bc5-work/exp0360/<variant>/kyty_emulator.
# The shared host tree's src/libs/bc5LleAgc.cpp, src/loader/runtimeLinker.cpp and src/kernel/pthread.cpp are copied with
# their sibling includes into a PRIVATE source tree, the given perl patches are applied there in order, the units the
# patches changed are compiled with the shared normal build's compdb commands into private objects, and the shared
# link command runs with those objects (the shared backend archive as it is). ~/src/KytyPlus, the shared builds and the
# archive are only read.
# usage: build0360.sh <variant> <patch.pl>...   (on the box, the patches and build0360.py beside it; CPU only, nice 19)
set -u
VAR=${1:?a variant name}; shift
case "$VAR" in *[!a-z0-9]* | "") echo "the variant is lower-case letters and digits"; exit 1 ;; esac
[ $# -ge 1 ] || { echo "at least one patch"; exit 1; }
E=$HOME/bc5-work/exp0360; V=$E/$VAR; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}
UNITS="src/libs/bc5LleAgc.cpp src/loader/runtimeLinker.cpp src/kernel/pthread.cpp"
want_md5() { case "$1" in src/libs/bc5LleAgc.cpp) echo "${EXPECT_AGC:-e7cc2f60}" ;; src/loader/runtimeLinker.cpp) echo "${EXPECT_RTL:-e37ed5cd}" ;; src/kernel/pthread.cpp) echo "${EXPECT_PT:-46c7ac3a}" ;; esac; }
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$V/src
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^exp 0360 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
for u in $UNITS; do [ "$(m "$TREE/$u")" = "$(want_md5 "$u")" ] || { echo "$u is $(m "$TREE/$u"), not $(want_md5 "$u"): stop"; exit 1; }; done
[ -f "$HERE/build0360.py" ] || { echo "no build0360.py beside this script"; exit 1; }
for p in "$@"; do [ -f "$HERE/$p" ] || { echo "no $p beside this script"; exit 1; }; done
mkdir -p "$V"
echo "exp 0360 | build of ~/bc5-work/exp0360/$VAR/kyty_emulator ($*; host units patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0360 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$V/obj"
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
    diff -u "$TREE/$u" "$SRC/$u" > "$V/$(basename "$u")-0360.diff"
    echo "$u: $(grep -c '^[-+][^-+]' "$V/$(basename "$u")-0360.diff") lines changed, $(grep -c 'experiment 0360' "$SRC/$u") marks, CRs $(tr -cd '\r' < "$TREE/$u" | wc -c) -> $(tr -cd '\r' < "$SRC/$u" | wc -c)"
  fi
done
[ -n "$CHANGED" ] || { echo "no unit changed"; exit 1; }
{ echo "shared binary md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH"); units:"; for u in $UNITS; do echo "  $u $(m "$TREE/$u")"; done; echo "changed:$CHANGED"; echo "patches:"; for p in "$@"; do echo "  $p $(m "$HERE/$p")"; done; } > "$V/build-inputs.txt"; cat "$V/build-inputs.txt"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$V/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$V/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
# shellcheck disable=SC2086
distrobox enter ubuntu -- python3 -I "$HERE/build0360.py" "$E/compdb.json" "$SRC" "$V/obj" "$B" "$BIN" $CHANGED > "$V/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$V/build.out"), warnings $(grep -c 'warning:' "$V/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$V/build.out" | head -20
grep -n "warning:" "$V/build.out" | sed 's/\x1b\[[0-9;]*m//g' | cut -c1-200 | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $V/build.out"; exit 1; }
m "$BIN" > "$V/binary.md5"; echo "md5 $(cat "$V/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$V/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: cpu meter $(strings "$BIN" | grep -c 'cpu meter:'), cpu prof $(strings "$BIN" | grep -c 'cpu prof:'), fast TLS $(strings "$BIN" | grep -c 'fast TLS stubs'), one TSC $(strings "$BIN" | grep -c 'BC5_0360_ONE_TSC'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $VAR $(cat "$V/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with$CHANGED of $* + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$E/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree units after:$(for u in $UNITS; do printf ' %s' "$(m "$TREE/$u")"; done)"
