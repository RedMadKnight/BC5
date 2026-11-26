#!/usr/bin/env bash
# BC5 experiment 0338, the integration (D19), only on the maintainer's yes for it: patch0338.py's five files (exp 0336's
# fixes and the posix NIDs on the posix entry points) into the shared tree ~/src/KytyPlus (f266548 + patch 0001), and both
# shared emulators rebuilt in place. The diff is made here from the tree's files and the private build's patched copies
# (~/bc5-work/exp0338/src, written by patch0338.py from the same md5-checked files), so its line endings are the files'
# own (kernel/pthread.cpp is CRLF); git apply --check, then git apply; each file must then equal the patched copy the
# private binaries were built from. The tree's diff against f266548 is written out as the candidate for
# backend/kytyplus-patches/0001-bc5-lle-agc.patch (main's copy must match what the shared builds were built from). The
# five files and both binaries are backed up under ~/bc5-work/exp0338/integration/; the undo is printed at the end.
# usage: int0338.sh   (on the box, after run0338.sh build and passed test runs; CPU only, under the BOX-LOCK; no emulator)
set -u
W=$HOME/bc5-work; E=$W/exp0338; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
EXPECT_NORMAL=4a146894; EXPECT_LEAN=c28cdd3c
declare -A TREE=(
  [src/libs/libKernel.cpp]=35b61eea1ca5f8b11f04e1e51c0016b8
  [src/kernel/pthread.cpp]=d1ab5a056ed8e3a184c5dbaa8d46e210
  [src/kernel/pthread.h]=f51b5ef1e1917f9df71c55ac2c94acaf
  [src/libs/bc5LleAgc.cpp]=5bccbb808c397f3180330425917b04c6
  [src/loader/runtimeLinker.cpp]=f294dfc28ec7558552d6b3898dbde71d
)
FILES="src/libs/libKernel.cpp src/kernel/pthread.cpp src/kernel/pthread.h src/libs/bc5LleAgc.cpp src/loader/runtimeLinker.cpp"
m() { md5sum < "$1" | cut -c1-8; }
M() { md5sum < "$1" | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -e "$I" ] && { echo "$I exists (integrated already?): stop"; exit 1; }
for f in $FILES; do
  [ "$(M "$K/$f")" = "${TREE[$f]}" ] || { echo "the tree's $f is $(M "$K/$f"), not ${TREE[$f]}: stop"; exit 1; }
  [ -s "$E/$f" ] || { echo "no patched copy $E/$f: stop"; exit 1; }
done
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$NB"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$LB")" = "$EXPECT_LEAN" ] || { echo "the shared lean binary is $(m "$LB"), not $EXPECT_LEAN: stop"; exit 1; }
[ -s "$E/binary.md5" ] && [ -s "$E/lean/binary.md5" ] || { echo "no private builds of 0338: stop"; exit 1; }
for t in N1 L1; do grep -qx pass "$E/raw/$t-verdict.txt" 2> /dev/null || { echo "the test run $t did not pass: stop"; exit 1; }; done
echo "cloud exp 0338 | integration: patch0338.py's five files into ~/src/KytyPlus, both shared emulators rebuilt (cmake, -j8, nice 10, CPU only, no emulator) | start $(date +%H:%M) | until ~$(date -d +40min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0338 | integration" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$I/tree-before" || exit 1
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), tree $(cd "$K" && git log -1 --format=%h), $(cd "$K" && git status --short | wc -l) changed entries"
  for f in $FILES; do echo "  $f tree $(m "$K/$f") ($(tr -cd '\r' < "$K/$f" | wc -c) CR) -> patched $(m "$E/$f") ($(tr -cd '\r' < "$E/$f" | wc -c) CR)"; done; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0338" && cp -p "$LB" "$I/kyty_emulator-lean.before-0338" || { echo "binary backup failed"; exit 1; }
for f in $FILES; do mkdir -p "$I/tree-before/$(dirname "$f")" && cp -p "$K/$f" "$I/tree-before/$f" || { echo "tree backup failed at $f"; exit 1; }; done
# the diff, with the files' own line endings
: > "$I/patch_0338.apply.diff"
for f in $FILES; do diff -u --label "a/$f" --label "b/$f" "$K/$f" "$E/$f" >> "$I/patch_0338.apply.diff"; [ $? = 1 ] || { echo "diff of $f failed or found no change: stop"; exit 1; }; done
echo "== $(date +%T) git apply --check ($(wc -l < "$I/patch_0338.apply.diff") lines, md5 $(m "$I/patch_0338.apply.diff"))"
(cd "$K" && git apply --check "$I/patch_0338.apply.diff") || { echo "git apply --check failed: nothing changed"; exit 1; }
(cd "$K" && git apply "$I/patch_0338.apply.diff") || { echo "git apply failed: restore from $I/tree-before"; exit 1; }
for f in $FILES; do cmp -s "$K/$f" "$E/$f" || { echo "$f differs from the private build's copy after git apply: restore from $I/tree-before"; exit 1; }; done
UNDO="cp -p $I/kyty_emulator.before-0338 $NB; cp -p $I/kyty_emulator-lean.before-0338 $LB; for f in $FILES; do cp -p $I/tree-before/\$f $K/\$f; done"
for v in normal lean; do
  bd=$W/kytyplus-build; [ $v = lean ] && bd=$W/kytyplus-build-lean
  echo "== $(date +%T) $v build"
  distrobox enter ubuntu -- nice -n 10 cmake --build "$bd" --target kyty_emulator -j8 > "$I/build-$v.out" 2>&1 || { tail -30 "$I/build-$v.out"; echo "$v build FAILED; undo: $UNDO; then rebuild both"; exit 1; }
done
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] || { echo "the normal binary did not change: stop"; exit 1; }
[ "$LM" != "$EXPECT_LEAN" ] || { echo "the lean binary did not change: stop"; exit 1; }
echo "strings: normal $(strings "$NB" | grep -c 'BC5_IMPORT_LOG\|Posix::sched_yield\|Posix::pthread_cond_destroy'), lean $(strings "$LB" | grep -c 'BC5_IMPORT_LOG\|Posix::sched_yield\|Posix::pthread_cond_destroy')"
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); errors: $(cat "$I"/build-*.out | grep -c 'error:')"
# the candidate patch 0001 (D19): the tree's whole diff against f266548
(cd "$K" && git add -N . && git diff --no-color f266548 > "$I/0001-bc5-lle-agc.patch.0338") && echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0338") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0338")"
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, tree $(cd "$K" && git status --short | wc -l) changed entries"
  for f in $FILES; do echo "  $f $(m "$K/$f")"; done; } | tee "$I/new-md5.txt"
echo "== $(date +%T) done; undo: $UNDO; then rebuild both"
