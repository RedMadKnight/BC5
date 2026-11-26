#!/usr/bin/env bash
# BC5 experiment 0343 (exp 0329's pattern for a host unit): one private emulator, ~/bc5-work/exp0343/kyty_emulator -
# the shared host tree's src/libs/bc5LleAgc.cpp (patch 0001 as main 12716e3b made it, md5 cfeec2f8) copied into a
# PRIVATE source tree, patch0343.pl applied there (the soft CP's label polls journaled, a replay's poll bounded by
# BC5_DIRECT_SOFT_WAIT_MS), the unit compiled with the shared normal build's compdb command into a private object,
# the shared link command run with that object and experiment 0346's private archive (ad7c2cb0, the third version +
# the lazy mapping table) in place of the shared ones. ~/src/KytyPlus, the shared builds and the shared archive are only
# read. usage: build0343.sh   (on the box, with patch0343.pl and build0343.py beside it; CPU only, nice 19, ~2 min)
set -u
E=$HOME/bc5-work/exp0343; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
PRIV_ARCH=$HOME/bc5-work/exp0346/backend-build/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-44ba4435}; EXPECT_NORMAL=${EXPECT_NORMAL:-ddfb9456}; EXPECT_PRIV=${EXPECT_PRIV:-ad7c2cb0}; EXPECT_SRC=${EXPECT_SRC:-cfeec2f8}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; UNIT=src/libs/bc5LleAgc.cpp
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$PRIV_ARCH")" = "$EXPECT_PRIV" ] || { echo "0346's private archive is $(m "$PRIV_ARCH"), not $EXPECT_PRIV: stop"; exit 1; }
[ "$(m "$TREE/$UNIT")" = "$EXPECT_SRC" ] || { echo "$TREE/$UNIT is $(m "$TREE/$UNIT"), not $EXPECT_SRC (main 12716e3b's patch 0001): stop"; exit 1; }
[ -f "$HERE/patch0343.pl" ] && [ -f "$HERE/build0343.py" ] || { echo "no patch0343.pl / build0343.py beside this script"; exit 1; }
echo "bvh exp 0343 | build of ~/bc5-work/exp0343/kyty_emulator (the host unit bc5LleAgc.cpp patched in a private copy, compiled, relinked with 0346's archive; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +8min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0343 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs"
cp "$TREE/$UNIT" "$SRC/$UNIT" || exit 1
perl "$HERE/patch0343.pl" "$SRC" > "$R/patch.out" 2>&1 || { echo "patch0343.pl failed:"; cat "$R/patch.out"; exit 1; }
cat "$R/patch.out"
diff -u "$TREE/$UNIT" "$SRC/$UNIT" > "$R/bc5LleAgc-0343.diff"; echo "diff: $(grep -c '^[-+][^-+]' "$R/bc5LleAgc-0343.diff") lines changed, $(grep -c 'experiment 0343' "$SRC/$UNIT") marks, CR $(tr -cd '\r' < "$SRC/$UNIT" | wc -c)"
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); 0346 archive $(m "$PRIV_ARCH"); $UNIT shared $(m "$TREE/$UNIT") patched $(m "$SRC/$UNIT"); patch0343.pl $(m "$HERE/patch0343.pl")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0343.py" "$E/compdb.json" "$SRC" "$E" "$B" "$ARCH" "$PRIV_ARCH" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL, 0346 cc0d24ce)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: soft-cp wait line $(strings "$BIN" | grep -c 'soft-cp wait: t'), slow post line $(strings "$BIN" | grep -c 'slow post: t'), waits polled $(strings "$BIN" | grep -c 'waits polled'), 0346 switch line $(strings "$BIN" | grep -c 'experiment 0346 switch'), 0341 switches line $(strings "$BIN" | grep -c 'experiment 0341 switches')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with bc5LleAgc.cpp.o of patch0343.pl + experiment 0346's archive $EXPECT_PRIV (a98c8b2); rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree unit after: $(m "$TREE/$UNIT") (want $EXPECT_SRC)"
