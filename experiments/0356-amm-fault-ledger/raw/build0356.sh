#!/usr/bin/env bash
# BC5 experiment 0356: one private emulator, ~/bc5-work/exp0356/kyty_emulator — the shared host tree's
# src/libs/libAmpr.cpp, src/kernel/memory.cpp and src/loader/runtimeLinker.cpp copied into a PRIVATE source tree,
# ammLedger.h put beside libAmpr.cpp, patch0356.pl applied there (the AMM command ledger; a fault on a page whose map
# is pending waits for it; the faulting instruction printed), the ledger's test built and run, the three units compiled
# with the shared normal build's compdb commands into private objects, the shared link command run with those
# objects (the shared backend archive as it is). ~/src/KytyPlus, the shared builds and the archive are only read.
# usage: build0356.sh   (on the box, with patch0356.pl, build0356.py, ammLedger.h and AmmLedgerTests.cpp beside it; CPU only, nice 19, ~4 min)
set -u
E=$HOME/bc5-work/exp0356; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}
EXPECT_AMPR=${EXPECT_AMPR:-93bdfe77}; EXPECT_MEM=${EXPECT_MEM:-11b1df22}; EXPECT_RTL=${EXPECT_RTL:-e37ed5cd}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && ! grep -q "^bvh exp 0356 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/libs/libAmpr.cpp")" = "$EXPECT_AMPR" ] || { echo "libAmpr.cpp is $(m "$TREE/src/libs/libAmpr.cpp"), not $EXPECT_AMPR: stop"; exit 1; }
[ "$(m "$TREE/src/kernel/memory.cpp")" = "$EXPECT_MEM" ] || { echo "memory.cpp is $(m "$TREE/src/kernel/memory.cpp"), not $EXPECT_MEM: stop"; exit 1; }
[ "$(m "$TREE/src/loader/runtimeLinker.cpp")" = "$EXPECT_RTL" ] || { echo "runtimeLinker.cpp is $(m "$TREE/src/loader/runtimeLinker.cpp"), not $EXPECT_RTL: stop"; exit 1; }
for f in patch0356.pl build0356.py ammLedger.h AmmLedgerTests.cpp; do [ -f "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
echo "bvh exp 0356 | build of ~/bc5-work/exp0356/kyty_emulator (three host units patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0356 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/kernel" "$SRC/src/loader" "$E/test"
cp "$TREE/src/libs/libAmpr.cpp" "$SRC/src/libs/" && cp "$TREE/src/kernel/memory.cpp" "$SRC/src/kernel/" && cp "$TREE/src/loader/runtimeLinker.cpp" "$SRC/src/loader/" || exit 1
cp "$HERE/ammLedger.h" "$SRC/src/libs/ammLedger.h" || exit 1
for d in kernel libs loader; do for f in "$TREE"/src/$d/*.inc "$TREE"/src/$d/*.h; do [ -e "$f" ] && cp "$f" "$SRC/src/$d/"; done; done  # the units' sibling includes (memoryAddressSpace.inc)
perl "$HERE/patch0356.pl" "$SRC" > "$R/patch.out" 2>&1 || { echo "patch0356.pl failed:"; cat "$R/patch.out"; exit 1; }
cat "$R/patch.out"
for u in src/libs/libAmpr.cpp src/kernel/memory.cpp src/loader/runtimeLinker.cpp; do diff -u "$TREE/$u" "$SRC/$u" > "$R/$(basename "$u")-0356.diff"; echo "$u: $(grep -c '^[-+][^-+]' "$R/$(basename "$u")-0356.diff") lines changed, $(grep -c 'experiment 0356' "$SRC/$u") marks"; done
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); units libAmpr $(m "$TREE/src/libs/libAmpr.cpp") memory $(m "$TREE/src/kernel/memory.cpp") runtimeLinker $(m "$TREE/src/loader/runtimeLinker.cpp"); patch0356.pl $(m "$HERE/patch0356.pl"); ammLedger.h $(m "$HERE/ammLedger.h")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
echo "== $(date +%T) the ledger's test"
cp "$HERE/AmmLedgerTests.cpp" "$E/test/" && cp "$HERE/ammLedger.h" "$E/test/"
distrobox enter ubuntu -- sh -c "cd '$E/test' && nice -n 19 clang++ -std=c++20 -O1 -Wall -Wextra -o AmmLedgerTests AmmLedgerTests.cpp && ./AmmLedgerTests" > "$R/ledger-test.out" 2>&1
trc=$?; tail -3 "$R/ledger-test.out"; echo "== ledger test rc $trc"
[ $trc = 0 ] || { echo "the ledger test FAILED"; exit 2; }
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0356.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: amm fault line $(strings "$BIN" | grep -c 'amm fault: 0x'), ledger line $(strings "$BIN" | grep -c 'amm ledger:'), new exit line $(strings "$BIN" | grep -c 'no pending map covers it'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with libAmpr/memory/runtimeLinker of patch0356.pl + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree units after: $(m "$TREE/src/libs/libAmpr.cpp") $(m "$TREE/src/kernel/memory.cpp") $(m "$TREE/src/loader/runtimeLinker.cpp")"
