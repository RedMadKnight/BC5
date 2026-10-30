#!/usr/bin/env bash
# Exp 0383, PORT-NP / PORT-LIBC: the Linux check that the laptop cannot do. CPU only, nice 19, no emulator and no GPU, under
# its own lock line, after a GO. Rebuilds the patched tree from ~/src/KytyPlus's f266548 and the branch's patch 0001 in a
# private directory, proves it against the pinned src tree, compiles the two fixed units and their unfixed copies with the
# shared build's flags, relinks a private kyty_emulator (never run) and runs the tests. Nothing shared is written;
# ~/src/KytyPlus and the shared build are only read. Stops at the first mismatch.
# The pins are in pins.env beside this script and nothing overrides them: a new pin is a new commit and a new review.
# A pass is the last line "boxcheck: PASS" and exit 0, and nothing else is.
# usage: boxcheck_port.sh   from the unpacked archive; ~15 min
set -u
# The box's locale is pl_PL: diff's and the tools' words below are compared as text (the first run stopped on "Pliki").
export LC_ALL=C LANGUAGE=C
E=$HOME/bc5-work/exp0383/run2; R=$E/raw; T=$E/tree; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
PATCH=$ROOT/backend/kytyplus-patches/0001-bc5-lle-agc.patch
unset PIN_PATCH_MD5 PIN_SRC_TREE PIN_SHARED_MD5 PIN_BASE_LIBC_SHA256 PIN_BASE_NP_SHA256
# shellcheck source=pins.env
. "$HERE/pins.env" || { echo "no pins.env"; exit 1; }
readonly PIN_PATCH_MD5 PIN_SRC_TREE PIN_SHARED_MD5 PIN_BASE_LIBC_SHA256 PIN_BASE_NP_SHA256
md5() { md5sum < "$1" | cut -d' ' -f1; }
sha() { sha256sum < "$1" | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5 "$PATCH")" = "$PIN_PATCH_MD5" ] || { echo "the patch is $(md5 "$PATCH"), not $PIN_PATCH_MD5: stop"; exit 1; }
SHARED_BEFORE=$(md5 "$B/src/kyty_emulator")
[ "$SHARED_BEFORE" = "$PIN_SHARED_MD5" ] || { echo "the shared normal binary is $SHARED_BEFORE, not $PIN_SHARED_MD5: stop"; exit 1; }
[ "$(sha "$K/src/libs/libC.cpp")" = "$PIN_BASE_LIBC_SHA256" ] || { echo "the shared tree's libC.cpp is not the pinned baseline: stop"; exit 1; }
[ "$(sha "$K/src/libs/libNpCppWebApi.cpp")" = "$PIN_BASE_NP_SHA256" ] || { echo "the shared tree's libNpCppWebApi.cpp is not the pinned baseline: stop"; exit 1; }
for f in NpAliasTests.cpp LibcNidTests.cpp boxbuild_port.py np-cases.manifest; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
[ -s "$ROOT/experiments/0328-npcppwebapi-port/NpCppWebApiTests.cpp" ] || { echo "no exp 0328 test file"; exit 1; }
[ -e "$T" ] && { echo "$T exists: stop (a new run tag, or move it aside)"; exit 1; }
mkdir -p "$R" "$T"
echo "top exp 0383 | CPU check of the NP and libc fixes (four units compiled, private relink, tests; nice 19, no emulator, no GPU) | start $(date +%H:%M) | until ~$(date -d +20min +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp 0383 | CPU check" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT

echo "== $(date +%T) tree from f266548 + the patch"
git -C "$K" -c core.autocrlf=false archive f266548 | tar -x -C "$T" || { echo "archive failed"; exit 1; }
git -C "$T" init -q; git -C "$T" config core.filemode false; git -C "$T" config core.autocrlf false; git -C "$T" config core.safecrlf false
git -C "$T" apply --check "$PATCH" 2> "$R/apply-check.err"; rc=$?; echo "apply --check rc $rc"; [ $rc = 0 ] || { head "$R/apply-check.err"; exit 1; }
git -C "$T" apply --whitespace=nowarn "$PATCH" || { echo "apply failed"; exit 1; }
git -C "$T" add -A src 2> /dev/null; TREE=$(git -C "$T" write-tree --prefix=src/)
echo "src tree $TREE"; [ "$TREE" = "$PIN_SRC_TREE" ] || { echo "not the pinned $PIN_SRC_TREE: stop"; exit 1; }
[ "$(grep -c 'exp 0372' "$PATCH")" = 5 ] && [ -s "$T/src/bc5/pad_audio_route.hpp" ] || { echo "exp 0372's pieces are not all there: stop"; exit 1; }
echo "exp 0372: 5 lines, pad_audio_route.hpp present"

# The units not rebuilt here come from the shared build: its tree must be this one but for the two fixed files, both of
# which must differ. The two lines below are the whole of what diff may say.
diff -rq "$K/src" "$T/src" > "$R/tree-diff.txt" 2>&1
{ echo "Files $K/src/libs/libC.cpp and $T/src/libs/libC.cpp differ"
  echo "Files $K/src/libs/libNpCppWebApi.cpp and $T/src/libs/libNpCppWebApi.cpp differ"; } > "$R/tree-diff-allowed.txt"
cmp -s "$R/tree-diff.txt" "$R/tree-diff-allowed.txt" || { echo "the shared tree differs from the patched tree beyond the two approved files, or not in both:"; head -20 "$R/tree-diff.txt"; echo "stop"; exit 1; }
echo "the shared tree differs in the two approved files only"

echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
mkdir -p "$E/tests"; cp "$HERE/NpAliasTests.cpp" "$HERE/LibcNidTests.cpp" "$HERE/np-cases.manifest" "$ROOT/experiments/0328-npcppwebapi-port/NpCppWebApiTests.cpp" "$E/tests/"
distrobox enter ubuntu -- sh -c 'clang++ --version | head -1; g++ --version | head -1; uname -r' > "$R/toolchain.txt" 2>&1

echo "== $(date +%T) compile, link, tests"
distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/boxbuild_port.py" "$E/compdb.json" "$T" "$E" "$B" "$E/tests" "$K" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc"
grep -an "error:\|FAILED\|FAIL\|== " "$R/build.out" | tail -50
[ -s "$E/warnings.txt" ] && cp "$E/warnings.txt" "$R/warnings.txt"
LAST=$(tail -n 1 "$R/build.out" | tr -d '\r')
SHARED_AFTER=$(md5 "$B/src/kyty_emulator")
echo "private binary $([ -f "$E/kyty_emulator" ] && md5 "$E/kyty_emulator") (not run); shared binary before $SHARED_BEFORE, after $SHARED_AFTER"
[ "$SHARED_AFTER" = "$PIN_SHARED_MD5" ] || { echo "boxcheck: FAIL: the shared binary changed during the run"; exit 5; }
[ $rc = 0 ] || { echo "boxcheck: FAIL: the build step's rc is $rc"; exit 6; }
case "$LAST" in
"== PASS: 0328 and libc final lines seen, np_alias_tests 30/30 "*", new warnings 0 of "*) ;;
*) echo "boxcheck: FAIL: rc 0 without the build step's final line"; exit 7 ;;
esac
echo "boxcheck: PASS"
