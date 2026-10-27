#!/usr/bin/env bash
# BC5 experiment 0337, the integration (D19), on the maintainer's words of 2026-10-27: "Integracja języka. Wprowadzenie
# poprawek do wszystkich buildow". patch0337.py's four files (SystemLanguage in the input configuration, the settings
# overlay's System tab, PARAM_ID_LANG from it) into the shared tree ~/src/KytyPlus (f266548 + patch 0001, exp 0338 in),
# and both shared emulators rebuilt in place, by exp 0338's int0338.sh steps: the diff is made from the tree's files and the
# private build's patched copies (~/bc5-work/exp0337/src, written by patch0337.py from the same md5-checked files, which
# exp 0338 did not touch), with the files' own line endings; git apply --check, then git apply; each file must then
# equal the copy the private binary ea557b2c was built from. The tree's diff against f266548 is written out as the
# candidate for backend/kytyplus-patches/0001-bc5-lle-agc.patch. The four files and both binaries are backed up under
# ~/bc5-work/exp0337/integration/; the undo is printed at the end.
# usage: int0337.sh   (on the box; CPU only, under the BOX-LOCK; no emulator)
set -u
W=$HOME/bc5-work; E=$W/exp0337; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
EXPECT_NORMAL=21e8bd22; EXPECT_LEAN=379a92b8   # after exp 0338 (F410)
declare -A TREE=(
  [src/graphics/presentation/window/hostInput.h]=a98cd3587a38376c936b7d24d18ab303
  [src/graphics/presentation/window/hostInput.cpp]=47f83afbf00f5cd1c9f8386a6433c8c0
  [src/libs/libSystemService.cpp]=c67a08e699de3a1500480bcb5be1d73a
  [src/graphics/presentation/settingsOverlay.cpp]=813dd1c9064c92a2a709a5adb69e616e
)
FILES="src/graphics/presentation/window/hostInput.h src/graphics/presentation/window/hostInput.cpp src/libs/libSystemService.cpp src/graphics/presentation/settingsOverlay.cpp"
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
[ "$(cat "$E/binary.md5" 2> /dev/null)" = ea557b2c ] || { echo "no private build ea557b2c of 0337: stop"; exit 1; }
grep -qx pass "$E/raw/L1-verdict.txt" 2> /dev/null || { echo "the test run L1 did not pass: stop"; exit 1; }
echo "cloud exp 0337 | integration: patch0337.py's four files into ~/src/KytyPlus, both shared emulators rebuilt (cmake, -j8, nice 10, CPU only, no emulator) | start $(date +%H:%M) | until ~$(date -d +40min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0337 | integration" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$I/tree-before" || exit 1
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), tree $(cd "$K" && git log -1 --format=%h), $(cd "$K" && git status --short | wc -l) changed entries"
  for f in $FILES; do echo "  $f tree $(m "$K/$f") ($(tr -cd '\r' < "$K/$f" | wc -c) CR) -> patched $(m "$E/$f") ($(tr -cd '\r' < "$E/$f" | wc -c) CR)"; done; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0337" && cp -p "$LB" "$I/kyty_emulator-lean.before-0337" || { echo "binary backup failed"; exit 1; }
for f in $FILES; do mkdir -p "$I/tree-before/$(dirname "$f")" && cp -p "$K/$f" "$I/tree-before/$f" || { echo "tree backup failed at $f"; exit 1; }; done
# the diff, with the files' own line endings
: > "$I/patch_0337.apply.diff"
for f in $FILES; do diff -u --label "a/$f" --label "b/$f" "$K/$f" "$E/$f" >> "$I/patch_0337.apply.diff"; [ $? = 1 ] || { echo "diff of $f failed or found no change: stop"; exit 1; }; done
echo "== $(date +%T) git apply --check ($(wc -l < "$I/patch_0337.apply.diff") lines, md5 $(m "$I/patch_0337.apply.diff"))"
(cd "$K" && git apply --check "$I/patch_0337.apply.diff") || { echo "git apply --check failed: nothing changed"; exit 1; }
(cd "$K" && git apply "$I/patch_0337.apply.diff") || { echo "git apply failed: restore from $I/tree-before"; exit 1; }
for f in $FILES; do cmp -s "$K/$f" "$E/$f" || { echo "$f differs from the private build's copy after git apply: restore from $I/tree-before"; exit 1; }; done
UNDO="cp -p $I/kyty_emulator.before-0337 $NB; cp -p $I/kyty_emulator-lean.before-0337 $LB; for f in $FILES; do cp -p $I/tree-before/\$f $K/\$f; done"
for v in normal lean; do
  bd=$W/kytyplus-build; [ $v = lean ] && bd=$W/kytyplus-build-lean
  echo "== $(date +%T) $v build"
  distrobox enter ubuntu -- nice -n 10 cmake --build "$bd" --target kyty_emulator -j8 > "$I/build-$v.out" 2>&1 || { tail -30 "$I/build-$v.out"; echo "$v build FAILED; undo: $UNDO; then rebuild both"; exit 1; }
done
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] || { echo "the normal binary did not change: stop"; exit 1; }
[ "$LM" != "$EXPECT_LEAN" ] || { echo "the lean binary did not change: stop"; exit 1; }
echo "strings: normal $(strings "$NB" | grep -c 'SystemLanguage\|Save##system'), lean $(strings "$LB" | grep -c 'SystemLanguage\|Save##system')"
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); errors: $(cat "$I"/build-*.out | grep -c 'error:')"
# the candidate patch 0001 (D19): the tree's whole diff against f266548
(cd "$K" && git add -N . && git diff --no-color f266548 > "$I/0001-bc5-lle-agc.patch.0337") && echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0337") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0337")"
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, tree $(cd "$K" && git status --short | wc -l) changed entries"
  for f in $FILES; do echo "  $f $(m "$K/$f")"; done; } | tee "$I/new-md5.txt"
echo "== $(date +%T) done; undo: $UNDO; then rebuild both"
