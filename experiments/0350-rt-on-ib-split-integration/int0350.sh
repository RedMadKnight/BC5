#!/usr/bin/env bash
# BC5 experiment 0350, the integration (the maintainer, 2026-10-28: "Tak, całość z 0349"), after his 18-minute RT-on play
# on exp 0349's test shortcut (F432): exactly what that test binary (fadeebd9) was built from goes into both shared builds:
#   1. the backend: exp 0349's eight files (0346 v3 host_indirect, 0348's carried register committed after the submit,
#      0349's ib_split, their tests, CMakeLists) from ~/bc5-work/exp0349/backend — md5-checked against branch
#      exp/0300-rt-dispatch-sync d37726e, every other source file there checked equal to the shared checkout — over
#      ~/src/bc5/backend, and the shared archive ~/bc5-work/backend-ubuntu/libbc5_backend.a rebuilt (ninja);
#   2. the host: exp 0343's src/libs/bc5LleAgc.cpp (the soft-CP replay polls bounded and journaled, e7cc2f60, made by
#      patch0343.pl from the tree's cfeec2f8) over ~/src/KytyPlus's;
#   3. both shared emulators rebuilt in place (ninja);
#   4. play-pkg.sh (normal and lean): the test launcher's one extra line, BC5_DIRECT_HOST_INDIRECT=learn:1100000000
#      BC5_DIRECT_SOFT_WAIT_MS=8, after the 0341 guards line; the cut needs no switch (default 0xf0000 dwords);
#   5. the host tree's diff against f266548 written out as the candidate for backend/kytyplus-patches/0001 (D19).
# input.cfg is not touched (RT on and Polish since exp 0342). Every replaced file, both binaries and the archive are
# backed up under ~/bc5-work/exp0350/integration/; the undo is printed at the end. ASTRO BOT's launcher is not touched.
# usage: int0350.sh   (on the box; CPU only, nice 19, under the BOX-LOCK; no emulator; ~20 min)
set -u
W=$HOME/bc5-work; E=$W/exp0350; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus; S=$HOME/src/bc5
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
EXPECT_NORMAL=${EXPECT_NORMAL:-ddfb9456}; EXPECT_LEAN=${EXPECT_LEAN:-03337c24}; EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-44ba4435}
UNIT=src/libs/bc5LleAgc.cpp; EXPECT_UNIT=cfeec2f8; UNIT_NEW=$W/exp0343/src/$UNIT; EXPECT_UNIT_NEW=e7cc2f60
LAUNCH=$W/play-pkg.sh; EXPECT_LAUNCH=${EXPECT_LAUNCH:-5b469087}; SRC49=$W/exp0349/backend
BFILES="CMakeLists.txt include/bc5/host_indirect.hpp include/bc5/ib_split.hpp src/direct.cpp src/host_indirect.cpp src/ib_split.cpp tests/host_indirect_test.cpp tests/ib_split_test.cpp"
WANT_MD5="8c02fb60 c9f68384 6b1bba40 ddb3e393 3457152d a2ba37ad 76a519af 0166c4fd"
GUARDS='export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels'
NEW_LINE='export BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8  # exp 0350 (F432): exp 0346 v3 (a GFX-form dispatch after the title zeroed base-1 resolved by the host, rewritten only to a page it read, else NOP-ed) + exp 0343 (soft-CP replay polls bounded at 8 ms); the exp 0349 cut is on by default'
m() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$I/backend-before" "$I/tree-before"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$NB"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$LB")" = "$EXPECT_LEAN" ] || { echo "the shared lean binary is $(m "$LB"), not $EXPECT_LEAN: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(git -C "$S" log -1 --format=%h)" = d0c2668 ] && [ -z "$(git -C "$S" status --porcelain -- backend)" ] || { echo "$S is not a clean d0c2668 in backend/: stop"; exit 1; }
[ "$(m "$K/$UNIT")" = "$EXPECT_UNIT" ] || { echo "$K/$UNIT is $(m "$K/$UNIT"), not $EXPECT_UNIT: stop"; exit 1; }
[ "$(m "$UNIT_NEW")" = "$EXPECT_UNIT_NEW" ] || { echo "$UNIT_NEW is $(m "$UNIT_NEW"), not $EXPECT_UNIT_NEW: stop"; exit 1; }
[ "$(m "$LAUNCH")" = "$EXPECT_LAUNCH" ] || { echo "$LAUNCH is $(m "$LAUNCH"), not $EXPECT_LAUNCH: stop"; exit 1; }
[ "$(grep -cxF -- "$GUARDS" "$LAUNCH")" = 1 ] || { echo "the guards line is not in $LAUNCH exactly once: stop"; exit 1; }
grep -q '^export BC5_DIRECT_HOST_INDIRECT=' "$LAUNCH" && { echo "$LAUNCH already sets BC5_DIRECT_HOST_INDIRECT: stop"; exit 1; }
set -- $WANT_MD5
for f in $BFILES; do [ "$(m "$SRC49/$f")" = "$1" ] || { echo "$SRC49/$f is $(m "$SRC49/$f"), not $1 (the branch's): stop"; exit 1; }; shift; done
# every other source file of the copy must equal the shared checkout's: nothing else of the test build may differ
other=0
while IFS= read -r f; do
  case " $BFILES " in *" $f "*) continue ;; esac
  if [ ! -f "$S/backend/$f" ] || ! cmp -s "$SRC49/$f" "$S/backend/$f"; then echo "differs from the shared checkout: $f"; other=$((other + 1)); fi
done < <(cd "$SRC49" && find . -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name 'CMakeLists.txt' \) | sed 's#^\./##' | sort)
[ "$other" = 0 ] || { echo "$other other file(s) of $SRC49 differ from $S/backend: stop"; exit 1; }
echo "exp 0350 | integration: exp 0349's backend (0346 v3 + 0348 + the IB cut) and exp 0343's host unit into the shared trees, the archive and both shared emulators rebuilt (ninja, CPU only, nice 19, no emulator); play-pkg.sh + HOST_INDIRECT/SOFT_WAIT | start $(date +%H:%M) | until ~$(date -d +25min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0350 | integration" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
(cd "$K" && git diff --no-color f266548) > "$I/0001-bc5-lle-agc.patch.before"
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), $S $(git -C "$S" log -1 --format=%h), tree $(cd "$K" && git log -1 --format=%h) with $(cd "$K" && git status --short | wc -l) changed entries, its diff (patch 0001 as built) md5 $(m "$I/0001-bc5-lle-agc.patch.before"), $UNIT $(m "$K/$UNIT"), play-pkg.sh $(m "$LAUNCH")"
  for f in $BFILES; do echo "  backend/$f $( [ -f "$S/backend/$f" ] && m "$S/backend/$f" || echo new) -> $(m "$SRC49/$f")"; done; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0350" && cp -p "$LB" "$I/kyty_emulator-lean.before-0350" && cp -p "$ARCH" "$I/libbc5_backend.a.before-0350" || { echo "binary backup failed"; exit 1; }
for f in $BFILES; do [ -f "$S/backend/$f" ] || continue; mkdir -p "$I/backend-before/$(dirname "$f")" && cp -p "$S/backend/$f" "$I/backend-before/$f" || { echo "backend backup failed at $f"; exit 1; }; done
mkdir -p "$I/tree-before/$(dirname "$UNIT")" && cp -p "$K/$UNIT" "$I/tree-before/$UNIT" && cp -p "$LAUNCH" "$I/play-pkg.sh.before-0350" || { echo "backup failed"; exit 1; }
UNDO="cp -p $I/kyty_emulator.before-0350 $NB; cp -p $I/kyty_emulator-lean.before-0350 $LB; cp -p $I/libbc5_backend.a.before-0350 $ARCH; git -C $S checkout -- backend; rm -f $S/backend/include/bc5/host_indirect.hpp $S/backend/include/bc5/ib_split.hpp $S/backend/src/host_indirect.cpp $S/backend/src/ib_split.cpp $S/backend/tests/host_indirect_test.cpp $S/backend/tests/ib_split_test.cpp; cp -p $I/tree-before/$UNIT $K/$UNIT; cp -p $I/play-pkg.sh.before-0350 $LAUNCH"
echo "== $(date +%T) 1. backend files into $S/backend"
for f in $BFILES; do mkdir -p "$S/backend/$(dirname "$f")" && cp "$SRC49/$f" "$S/backend/$f" || { echo "copy failed at $f; undo: $UNDO"; exit 1; }; done
echo "== $(date +%T) 2. exp 0343's host unit"
cp "$UNIT_NEW" "$K/$UNIT" && [ "$(m "$K/$UNIT")" = "$EXPECT_UNIT_NEW" ] || { echo "unit copy failed; undo: $UNDO"; exit 1; }
echo "== $(date +%T) 3a. the shared archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 ninja bc5_backend" > "$I/build-backend.out" 2>&1 || { tail -30 "$I/build-backend.out"; echo "archive build FAILED; undo: $UNDO"; exit 1; }
[ "$(m "$ARCH")" != "$EXPECT_ARCHIVE" ] || { echo "the archive did not change; undo: $UNDO"; exit 1; }
echo "archive $(m "$ARCH"); $(grep -c 'warning:' "$I/build-backend.out") warnings; objects: ib_split $(strings "$ARCH" | grep -c '^ib_split\.cpp\.o'), host_indirect $(strings "$ARCH" | grep -c '^host_indirect\.cpp\.o')"
echo "== $(date +%T) 3b. normal build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/build-normal.out" 2>&1 || { tail -30 "$I/build-normal.out"; echo "normal build FAILED; undo: $UNDO; then ninja both"; exit 1; }
echo "== $(date +%T) 3c. lean build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/build-lean.out" 2>&1 || { tail -30 "$I/build-lean.out"; echo "lean build FAILED (the normal one is rebuilt); undo: $UNDO; then ninja both"; exit 1; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] || { echo "a binary did not change (normal $NM, lean $LM); undo: $UNDO"; exit 1; }
for b in "$NB" "$LB"; do echo "strings $b: 0349 switch $(strings "$b" | grep -c 'experiment 0349: a job'), 0346 switch $(strings "$b" | grep -c 'experiment 0346 switch'), cs refused $(strings "$b" | grep -c 'cs refused rc'), soft-cp wait $(strings "$b" | grep -c 'soft-cp wait'), 0341 switches $(strings "$b" | grep -c 'experiment 0341 switches')"; done
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); recompiled: normal $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-normal.out"), lean $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-lean.out")"
echo "== $(date +%T) 4. play-pkg.sh: HOST_INDIRECT + SOFT_WAIT after the guards"
perl -e 'my ($f, $after, $new) = @ARGV; open my $in, "<", $f or die "$f: $!\n"; my @l = <$in>; close $in;
  my $n = grep { $_ eq "$after\n" } @l; die "the guards line occurs $n times\n" unless $n == 1;
  @l = map { $_ eq "$after\n" ? ($_, "$new\n") : $_ } @l;
  open my $out, ">", $f or die "$f: $!\n"; print {$out} @l; close $out or die "$f: $!\n";' "$LAUNCH" "$GUARDS" "$NEW_LINE" || { echo "launcher edit failed; undo: $UNDO"; exit 1; }
diff -u "$I/play-pkg.sh.before-0350" "$LAUNCH" > "$I/play-pkg-0350.diff"
[ "$(grep -c '^[-+][^-+]' "$I/play-pkg-0350.diff")" = 1 ] && bash -n "$LAUNCH" && [ -x "$LAUNCH" ] || { echo "the launcher's diff is not 1 line added, or it does not parse; undo: $UNDO"; exit 1; }
echo "== $(date +%T) 5. the candidate patch 0001"
(cd "$K" && git diff --no-color f266548) > "$I/0001-bc5-lle-agc.patch.0350"
echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0350") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0350") (before $(m "$I/0001-bc5-lle-agc.patch.before"))"
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m "$ARCH"), $UNIT $(m "$K/$UNIT"), play-pkg.sh $(m "$LAUNCH")"; } | tee "$I/new-md5.txt"
echo "normal=$NM lean=$LM archive=$(m "$ARCH") launcher=$(m "$LAUNCH")" > "$I/new-md5.env"
echo "== $(date +%T) done; undo: $UNDO; then ninja bc5_backend, and kyty_emulator in both builds (or keep the restored binaries)"
