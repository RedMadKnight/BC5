#!/usr/bin/env bash
# BC5 experiment 0360 (exp 0358's build0358v5.sh for one unit): one private emulator per variant,
# ~/bc5-work/exp0360/<variant>/kyty_emulator. The shared host tree's src/libs/bc5LleAgc.cpp is copied with its sibling
# includes into a PRIVATE source tree, the given perl patches are applied there in order, the unit is compiled with the
# shared normal build's compdb command into a private object, and the shared link command runs with that object (the
# shared backend archive as it is). ~/src/KytyPlus, the shared builds and the archive are only read.
# usage: build0360.sh <variant> <patch.pl>...   (on the box, the patches and build0360.py beside it; CPU only, nice 19)
set -u
VAR=${1:?a variant name}; shift
case "$VAR" in *[!a-z0-9]* | "") echo "the variant is lower-case letters and digits"; exit 1 ;; esac
[ $# -ge 1 ] || { echo "at least one patch"; exit 1; }
E=$HOME/bc5-work/exp0360; V=$E/$VAR; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}; EXPECT_AGC=${EXPECT_AGC:-e7cc2f60}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$V/src
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^exp 0360 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$EXPECT_AGC" ] || { echo "bc5LleAgc.cpp is $(m "$TREE/src/libs/bc5LleAgc.cpp"), not $EXPECT_AGC: stop"; exit 1; }
[ -f "$HERE/build0360.py" ] || { echo "no build0360.py beside this script"; exit 1; }
for p in "$@"; do [ -f "$HERE/$p" ] || { echo "no $p beside this script"; exit 1; }; done
mkdir -p "$V"
echo "exp 0360 | build of ~/bc5-work/exp0360/$VAR/kyty_emulator ($*; one host unit patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0360 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$V/obj"; mkdir -p "$SRC/src/libs"
cp "$TREE/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/" || exit 1
for f in "$TREE"/src/libs/*.inc "$TREE"/src/libs/*.h; do [ -e "$f" ] && cp "$f" "$SRC/src/libs/"; done  # the unit's sibling includes
: > "$V/patch.out"
for p in "$@"; do perl "$HERE/$p" "$SRC" >> "$V/patch.out" 2>&1 || { echo "patch $p failed:"; cat "$V/patch.out"; exit 1; }; done
cat "$V/patch.out"
diff -u "$TREE/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/bc5LleAgc.cpp" > "$V/bc5LleAgc.cpp-0360.diff"
echo "bc5LleAgc.cpp: $(grep -c '^[-+][^-+]' "$V/bc5LleAgc.cpp-0360.diff") lines changed, $(grep -c 'experiment 0360' "$SRC/src/libs/bc5LleAgc.cpp") marks"
{ echo "shared binary md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH"); unit bc5LleAgc $(m "$TREE/src/libs/bc5LleAgc.cpp"); patches:"; for p in "$@"; do echo "  $p $(m "$HERE/$p")"; done; } > "$V/build-inputs.txt"; cat "$V/build-inputs.txt"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$V/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$V/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0360.py" "$E/compdb.json" "$SRC" "$V/obj" "$B" "$BIN" > "$V/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$V/build.out"), warnings $(grep -c 'warning:' "$V/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$V/build.out" | head -20
grep -n "warning:" "$V/build.out" | grep -i "0360\|meter" | head -10
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $V/build.out"; exit 1; }
m "$BIN" > "$V/binary.md5"; echo "md5 $(cat "$V/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$V/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: cpu meter $(strings "$BIN" | grep -c 'cpu meter:'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $VAR $(cat "$V/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with bc5LleAgc of $* + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$E/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree unit after: $(m "$TREE/src/libs/bc5LleAgc.cpp") (want $EXPECT_AGC)"
