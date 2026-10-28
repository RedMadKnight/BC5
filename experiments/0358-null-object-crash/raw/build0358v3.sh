#!/usr/bin/env bash
# BC5 experiment 0358, trap v3 (build0358.sh's pattern): one private emulator, ~/bc5-work/exp0358/kyty_emulator — the
# shared host tree's src/kernel/pthread.cpp, src/loader/runtimeLinker.cpp and src/libs/bc5LleAgc.cpp copied into a
# PRIVATE source tree with their sibling includes, patch0358.pl (the v1 trap) then patch0358v3.pl (the pool state at
# the fault, the TLS block journal, the per-second pool sample) applied there, the three units compiled with the shared
# normal build's compdb commands into private objects, the shared link command run with those objects (the shared
# backend archive as it is). ~/src/KytyPlus, the shared builds and the archive are only read; the previous private
# binary is kept beside the new one as kyty_emulator.<md5>.
# usage: build0358v2.sh   (on the box, with patch0358.pl, patch0358v3.pl and build0358v3.py beside it; CPU only, nice 19)
set -u
E=$HOME/bc5-work/exp0358; R=$E/raw-v3; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}
EXPECT_PT=${EXPECT_PT:-46c7ac3a}; EXPECT_RTL=${EXPECT_RTL:-e37ed5cd}; EXPECT_AGC=${EXPECT_AGC:-e7cc2f60}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src-v3
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^bvh exp 0358 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/kernel/pthread.cpp")" = "$EXPECT_PT" ] || { echo "pthread.cpp is $(m "$TREE/src/kernel/pthread.cpp"), not $EXPECT_PT: stop"; exit 1; }
[ "$(m "$TREE/src/loader/runtimeLinker.cpp")" = "$EXPECT_RTL" ] || { echo "runtimeLinker.cpp is $(m "$TREE/src/loader/runtimeLinker.cpp"), not $EXPECT_RTL: stop"; exit 1; }
[ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$EXPECT_AGC" ] || { echo "bc5LleAgc.cpp is $(m "$TREE/src/libs/bc5LleAgc.cpp"), not $EXPECT_AGC: stop"; exit 1; }
for f in patch0358.pl patch0358v3.pl build0358v3.py; do [ -f "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
echo "bvh exp 0358 | build of ~/bc5-work/exp0358/kyty_emulator, trap v3 (three host units patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0358 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/kernel" "$SRC/src/loader" "$SRC/src/libs"
cp "$TREE/src/kernel/pthread.cpp" "$SRC/src/kernel/" && cp "$TREE/src/loader/runtimeLinker.cpp" "$SRC/src/loader/" && cp "$TREE/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/" || exit 1
for d in kernel loader libs; do for f in "$TREE"/src/$d/*.inc "$TREE"/src/$d/*.h; do [ -e "$f" ] && cp "$f" "$SRC/src/$d/"; done; done  # the units' sibling includes
perl "$HERE/patch0358.pl" "$SRC" > "$R/patch.out" 2>&1 && perl "$HERE/patch0358v3.pl" "$SRC" >> "$R/patch.out" 2>&1 || { echo "a patch failed:"; cat "$R/patch.out"; exit 1; }
cat "$R/patch.out"
for u in src/kernel/pthread.cpp src/loader/runtimeLinker.cpp src/libs/bc5LleAgc.cpp; do diff -u "$TREE/$u" "$SRC/$u" > "$R/$(basename "$u")-0358v2.diff"; echo "$u: $(grep -c '^[-+][^-+]' "$R/$(basename "$u")-0358v2.diff") lines changed, $(grep -c 'experiment 0358' "$SRC/$u") marks"; done
grep -n 'tls block: t\|pool sample: t\|thread trap: base' "$SRC/src/loader/runtimeLinker.cpp" "$SRC/src/libs/bc5LleAgc.cpp"| cat -A | grep -c '\\n"' | { read n; echo "C newline escapes intact in $n of 3 new format lines"; }
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); units pthread $(m "$TREE/src/kernel/pthread.cpp") runtimeLinker $(m "$TREE/src/loader/runtimeLinker.cpp") bc5LleAgc $(m "$TREE/src/libs/bc5LleAgc.cpp"); patch0358.pl $(m "$HERE/patch0358.pl") patch0358v3.pl $(m "$HERE/patch0358v3.pl")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0358v3.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: thread trap lines $(strings "$BIN" | grep -c 'thread trap:'), pool sample $(strings "$BIN" | grep -c 'pool sample:'), tls block $(strings "$BIN" | grep -c 'tls block:'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with pthread/runtimeLinker/bc5LleAgc of patch0358.pl + patch0358v3.pl + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$E/raw/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree units after: $(m "$TREE/src/kernel/pthread.cpp") $(m "$TREE/src/loader/runtimeLinker.cpp") $(m "$TREE/src/libs/bc5LleAgc.cpp")"
