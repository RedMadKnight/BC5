#!/usr/bin/env bash
# BC5 experiment 0342, the integration (the maintainer, 2026-10-27: "Tak: zintegruj jedną kolejkę, oba zabezpieczenia
# 0341 i poprawkę listy języków do obu wspólnych buildów (normal i lean); w input.cfg RT on i polski."), after his
# RT-on play on exp 0341's test shortcut (F415):
#   1. the backend: exp 0341's nine files (the product staircase, the shadow labels, their switches in the Device) from
#      ~/bc5-work/exp0341/backend — the copy b052d860 was built from, md5-checked against main — over the shared
#      checkout ~/src/bc5/backend, and the shared archive ~/bc5-work/backend-ubuntu/libbc5_backend.a rebuilt (ninja);
#   2. the host: deadzone0342.pl on ~/src/KytyPlus's settingsOverlay.cpp (the F2 language list scrolled by stick drift);
#   3. both shared emulators rebuilt in place (ninja; the archive is a link input, the changed backend headers and the
#      overlay recompile);
#   4. play-pkg.sh (the second title's launcher, normal and lean): COMPUTE_RING=-1 (one ring, F412) and the two guards
#      BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1 (F414) — the lines the test launcher played;
#   5. input.cfg: the test's private configuration exp0341/input-rton.cfg (RayTracing.PPSA03671=on, SystemLanguage=Polish,
#      the rest equal — checked) copied over it;
#   6. the host tree's diff against f266548 written out as the candidate for backend/kytyplus-patches/0001 (D19).
# Every replaced file and both binaries and the archive are backed up under ~/bc5-work/exp0342/integration/; the undo
# is printed at the end. ASTRO BOT's launcher (play-astro-compute.sh) is not touched.
# usage: int0342.sh   (on the box, deadzone0342.pl beside it; CPU only, nice 19, under the BOX-LOCK; no emulator; ~20 min)
set -u
W=$HOME/bc5-work; E=$W/exp0342; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus; S=$HOME/src/bc5
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
EXPECT_NORMAL=${EXPECT_NORMAL:-9382b1e9}; EXPECT_LEAN=${EXPECT_LEAN:-1860613a}; EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-825ae1d1}
OVL=src/graphics/presentation/settingsOverlay.cpp; EXPECT_OVL=454106a4
LAUNCH=$W/play-pkg.sh; EXPECT_LAUNCH=${EXPECT_LAUNCH:-b10eac6d}
CFG=$W/input.cfg; CFG_NEW=$W/exp0341/input-rton.cfg; SRC41=$W/exp0341/backend
HERE=$(cd "$(dirname "$0")" && pwd)
# exp 0341's backend files as built into b052d860 and as on main (from branch exp/0300-rt-dispatch-sync f0fc75d)
BFILES="CMakeLists.txt include/bc5/indirect_check.hpp include/bc5/policy.hpp include/bc5/shadow_labels.hpp src/direct.cpp src/indirect_check.cpp src/shadow_labels.cpp tests/indirect_check_test.cpp tests/shadow_labels_test.cpp"
WANT_MD5="e7d80fff 8a359bf6 2084cd6c a8bf0059 c802cc89 282ee35e 2cfbea8b d3d63d86 06cf2eb2"
OLD_RING='export BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_CROSS_RING_WAITS=all'
NEW_RING='export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all  # exp 0342 (F412, F415): one ring - every compute buffer on the GFX ring (was 0)'
NEW_GUARDS='export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels'
m() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$I/backend-before" "$I/tree-before"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -f "$HERE/deadzone0342.pl" ] || { echo "no deadzone0342.pl beside this script"; exit 1; }
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$NB"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
[ "$(m "$LB")" = "$EXPECT_LEAN" ] || { echo "the shared lean binary is $(m "$LB"), not $EXPECT_LEAN: stop (EXPECT_LEAN=... to accept)"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop (EXPECT_ARCHIVE=... to accept)"; exit 1; }
[ "$(git -C "$S" log -1 --format=%h)" = cc6a3bc ] && [ -z "$(git -C "$S" status --porcelain -- backend)" ] || { echo "$S is not a clean cc6a3bc in backend/: stop"; exit 1; }
[ "$(m "$K/$OVL")" = "$EXPECT_OVL" ] || { echo "$OVL is $(m "$K/$OVL"), not $EXPECT_OVL: stop"; exit 1; }
[ "$(m "$LAUNCH")" = "$EXPECT_LAUNCH" ] || { echo "$LAUNCH is $(m "$LAUNCH"), not $EXPECT_LAUNCH: stop (EXPECT_LAUNCH=... after checking the ring line)"; exit 1; }
[ "$(grep -cxF -- "$OLD_RING" "$LAUNCH")" = 1 ] || { echo "the ring line [$OLD_RING] is not in $LAUNCH exactly once: stop"; exit 1; }
grep -qx 'export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_DMA_SYNC=1' "$LAUNCH" || { echo "$LAUNCH does not turn the CP check on (BC5_DIRECT_GPU_CHECK=1): the staircase would do nothing: stop"; exit 1; }
grep -qx 'RayTracing.PPSA03671=on' "$CFG_NEW" && grep -qx 'SystemLanguage=Polish' "$CFG_NEW" || { echo "$CFG_NEW lacks RayTracing.PPSA03671=on or SystemLanguage=Polish: stop"; exit 1; }
rest() { grep -v -i -e '^RayTracing\.PPSA03671=' -e '^SystemLanguage=' "$1" | sort; }
[ "$(rest "$CFG" | md5sum)" = "$(rest "$CFG_NEW" | md5sum)" ] || { echo "$CFG_NEW differs from $CFG in more than the RT and language lines: stop"; diff <(rest "$CFG") <(rest "$CFG_NEW"); exit 1; }
set -- $WANT_MD5
for f in $BFILES; do [ "$(m "$SRC41/$f")" = "$1" ] || { echo "$SRC41/$f is $(m "$SRC41/$f"), not $1 (main's): stop"; exit 1; }; shift; done
echo "exp 0342 | integration: exp 0341's backend + the overlay's dead zone into the shared trees, the archive and both shared emulators rebuilt (ninja, CPU only, nice 19, no emulator); play-pkg.sh one ring + guards; input.cfg RT on + Polish | start $(date +%H:%M) | until ~$(date -d +25min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0342 | integration" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
(cd "$K" && git diff --no-color f266548) > "$I/0001-bc5-lle-agc.patch.before"
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), $S $(git -C "$S" log -1 --format=%h), tree $(cd "$K" && git log -1 --format=%h) with $(cd "$K" && git status --short | wc -l) changed entries, its diff (patch 0001 as built) md5 $(m "$I/0001-bc5-lle-agc.patch.before"), $OVL $(m "$K/$OVL"), play-pkg.sh $(m "$LAUNCH"), input.cfg $(m "$CFG")"
  for f in $BFILES; do echo "  backend/$f $( [ -f "$S/backend/$f" ] && m "$S/backend/$f" || echo new) -> $(m "$SRC41/$f")"; done; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0342" && cp -p "$LB" "$I/kyty_emulator-lean.before-0342" && cp -p "$ARCH" "$I/libbc5_backend.a.before-0342" || { echo "binary backup failed"; exit 1; }
for f in $BFILES; do [ -f "$S/backend/$f" ] || continue; mkdir -p "$I/backend-before/$(dirname "$f")" && cp -p "$S/backend/$f" "$I/backend-before/$f" || { echo "backend backup failed at $f"; exit 1; }; done
mkdir -p "$I/tree-before/$(dirname "$OVL")" && cp -p "$K/$OVL" "$I/tree-before/$OVL" && cp -p "$LAUNCH" "$I/play-pkg.sh.before-0342" && cp -p "$CFG" "$I/input.cfg.before-0342" || { echo "backup failed"; exit 1; }
UNDO="cp -p $I/kyty_emulator.before-0342 $NB; cp -p $I/kyty_emulator-lean.before-0342 $LB; cp -p $I/libbc5_backend.a.before-0342 $ARCH; git -C $S checkout -- backend; rm -f $S/backend/include/bc5/shadow_labels.hpp $S/backend/src/shadow_labels.cpp $S/backend/tests/shadow_labels_test.cpp; cp -p $I/tree-before/$OVL $K/$OVL; cp -p $I/play-pkg.sh.before-0342 $LAUNCH; cp -p $I/input.cfg.before-0342 $CFG"
echo "== $(date +%T) 1. backend files into $S/backend"
for f in $BFILES; do mkdir -p "$S/backend/$(dirname "$f")" && cp "$SRC41/$f" "$S/backend/$f" || { echo "copy failed at $f; undo: $UNDO"; exit 1; }; done
echo "== $(date +%T) 2. the overlay's dead zone"
perl "$HERE/deadzone0342.pl" "$K/$OVL" || { echo "deadzone0342.pl failed (nothing written by it); undo: $UNDO"; exit 1; }
[ "$(grep -c 'past(-value)' "$K/$OVL")" = 2 ] || { echo "the overlay does not hold the two past(-value) calls; undo: $UNDO"; exit 1; }
echo "== $(date +%T) 3a. the shared archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 ninja bc5_backend" > "$I/build-backend.out" 2>&1 || { tail -30 "$I/build-backend.out"; echo "archive build FAILED; undo: $UNDO"; exit 1; }
[ "$(m "$ARCH")" != "$EXPECT_ARCHIVE" ] || { echo "the archive did not change; undo: $UNDO"; exit 1; }
echo "archive $(m "$ARCH"); $(grep -c 'warning:' "$I/build-backend.out") warnings; shadow_labels object: $(strings "$ARCH" | grep -c '^shadow_labels\.cpp\.o')"
echo "== $(date +%T) 3b. normal build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/build-normal.out" 2>&1 || { tail -30 "$I/build-normal.out"; echo "normal build FAILED; undo: $UNDO; then ninja both"; exit 1; }
echo "== $(date +%T) 3c. lean build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/build-lean.out" 2>&1 || { tail -30 "$I/build-lean.out"; echo "lean build FAILED (the normal one is rebuilt); undo: $UNDO; then ninja both"; exit 1; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] || { echo "a binary did not change (normal $NM, lean $LM); undo: $UNDO"; exit 1; }
echo "strings: normal 0341 switch lines $(strings "$NB" | grep -c 'experiment 0341 switches'), lean $(strings "$LB" | grep -c 'experiment 0341 switches')"
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); recompiled: normal $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-normal.out"), lean $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-lean.out")"
echo "== $(date +%T) 4. play-pkg.sh: one ring + the guards"
perl -e 'my ($f, $old, $ring, $guards) = @ARGV; open my $in, "<", $f or die "$f: $!\n"; my @l = <$in>; close $in;
  my $n = grep { $_ eq "$old\n" } @l; die "the ring line occurs $n times\n" unless $n == 1;
  @l = map { $_ eq "$old\n" ? ("$ring\n", "$guards\n") : $_ } @l;
  open my $out, ">", $f or die "$f: $!\n"; print {$out} @l; close $out or die "$f: $!\n";' "$LAUNCH" "$OLD_RING" "$NEW_RING" "$NEW_GUARDS" || { echo "launcher edit failed; undo: $UNDO"; exit 1; }
diff -u "$I/play-pkg.sh.before-0342" "$LAUNCH" > "$I/play-pkg-0342.diff"
[ "$(grep -c '^[-+][^-+]' "$I/play-pkg-0342.diff")" = 3 ] && bash -n "$LAUNCH" && [ -x "$LAUNCH" ] || { echo "the launcher's diff is not 1 line changed + 1 added, or it does not parse; undo: $UNDO"; exit 1; }
echo "== $(date +%T) 5. input.cfg: RT on + Polish"
cp "$CFG_NEW" "$CFG" || { echo "input.cfg copy failed; undo: $UNDO"; exit 1; }
diff "$I/input.cfg.before-0342" "$CFG" > "$I/input-cfg-0342.diff"
echo "== $(date +%T) 6. the candidate patch 0001"
(cd "$K" && git diff --no-color f266548) > "$I/0001-bc5-lle-agc.patch.0342"
echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0342") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0342") (before $(m "$I/0001-bc5-lle-agc.patch.before"))"
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m "$ARCH"), $OVL $(m "$K/$OVL"), play-pkg.sh $(m "$LAUNCH"), input.cfg $(m "$CFG")"; } | tee "$I/new-md5.txt"
echo "normal=$NM lean=$LM archive=$(m "$ARCH") launcher=$(m "$LAUNCH")" > "$I/new-md5.env"
echo "== $(date +%T) done; undo: $UNDO; then ninja bc5_backend, and kyty_emulator in both builds (or keep the restored binaries)"
