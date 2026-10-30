#!/usr/bin/env bash
# PORT-NP / PORT-LIBC: the Linux check that the laptop cannot do. CPU only, nice 19, no emulator and no GPU, under its
# own lock line, after a GO. Rebuilds the patched tree from ~/src/KytyPlus's f266548 and the branch's patch 0001 in a
# private directory, proves it against the pinned src tree, compiles libC.cpp and libNpCppWebApi.cpp with the shared
# build's flags, relinks a private kyty_emulator (never run) and runs the tests. Nothing shared is written;
# ~/src/KytyPlus and the shared build are only read. Stops at the first mismatch.
# usage: boxcheck_port.sh   from the unpacked archive; ~10 min
set -u
E=$HOME/bc5-work/port-host; R=$E/raw; T=$E/tree; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
PATCH=$ROOT/backend/kytyplus-patches/0001-bc5-lle-agc.patch
EXPECT_PATCH=${EXPECT_PATCH:-00a296dac4a5b3f73b66302afafba317}; EXPECT_SRC_TREE=${EXPECT_SRC_TREE:-7fab373ac309cf05b0f666dd8152601756d2df3d}; EXPECT_NORMAL=${EXPECT_NORMAL:-58c4a627}
m() { md5sum < "$1" | cut -c1-8; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$PATCH" | cut -d' ' -f1)" = "$EXPECT_PATCH" ] || { echo "the patch is not $EXPECT_PATCH: stop"; exit 1; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
for f in NpAliasTests.cpp LibcNidTests.cpp boxbuild_port.py; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
[ -s "$ROOT/experiments/0328-npcppwebapi-port/NpCppWebApiTests.cpp" ] || { echo "no exp 0328 test file"; exit 1; }
[ -e "$E" ] && { echo "$E exists: stop (a new run tag, or move it aside)"; exit 1; }
mkdir -p "$R" "$T"
echo "top exp port-host | CPU check of the NP and libc fixes (two units compiled, private relink, tests; nice 19, no emulator, no GPU) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp port-host | CPU check" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT

echo "== $(date +%T) tree from f266548 + the patch"
git -C "$K" -c core.autocrlf=false archive f266548 | tar -x -C "$T" || { echo "archive failed"; exit 1; }
git -C "$T" init -q; git -C "$T" config core.filemode false; git -C "$T" config core.autocrlf false
git -C "$T" apply --check "$PATCH" 2> "$R/apply-check.err"; rc=$?; echo "apply --check rc $rc"; [ $rc = 0 ] || { head "$R/apply-check.err"; exit 1; }
git -C "$T" apply --whitespace=nowarn "$PATCH" || { echo "apply failed"; exit 1; }
git -C "$T" add -A src; TREE=$(git -C "$T" write-tree --prefix=src/)
echo "src tree $TREE"; [ "$TREE" = "$EXPECT_SRC_TREE" ] || { echo "not the pinned $EXPECT_SRC_TREE: stop"; exit 1; }
[ "$(grep -c 'exp 0372' "$PATCH")" = 5 ] && [ -s "$T/src/bc5/pad_audio_route.hpp" ] || { echo "exp 0372's pieces are not all there: stop"; exit 1; }
echo "exp 0372: 5 lines, pad_audio_route.hpp present"

# the units not rebuilt here come from the shared build: its tree must be this one but for the two fixed files
diff -rq "$K/src" "$T/src" > "$R/tree-diff.txt" 2>&1
OTHER=$(grep -v 'libs/libC.cpp\|libs/libNpCppWebApi.cpp' "$R/tree-diff.txt" | wc -l)
echo "the shared tree differs in $(wc -l < "$R/tree-diff.txt") file(s), $OTHER beyond the two fixed"
[ "$OTHER" = 0 ] || [ "${ACCEPT_TREE_DIFF:-0}" = 1 ] || { head "$R/tree-diff.txt"; echo "stop (ACCEPT_TREE_DIFF=1 to accept)"; exit 1; }

echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
mkdir -p "$E/tests"; cp "$HERE/NpAliasTests.cpp" "$HERE/LibcNidTests.cpp" "$ROOT/experiments/0328-npcppwebapi-port/NpCppWebApiTests.cpp" "$E/tests/"
distrobox enter ubuntu -- sh -c 'clang++ --version | head -1; g++ --version | head -1; uname -r' > "$R/toolchain.txt" 2>&1

echo "== $(date +%T) compile, link, tests"
distrobox enter ubuntu -- python3 -I "$HERE/boxbuild_port.py" "$E/compdb.json" "$T" "$E" "$B" "$E/tests" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc"
grep -an "error:\|FAILED\|== " "$R/build.out" | tail -50
grep -c "warning:" "$R/build.out" | sed 's/^/warnings: /'
echo "private binary $(m "$E/kyty_emulator") (not run); shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL)"
exit $rc
