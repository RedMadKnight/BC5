#!/usr/bin/env bash
# BC5 exp 0412, build g412i (2026-11-11, README section 19): g412h with line tables (-g1) in the main unit, for the line-level
# stack profile of the render thread (prof0412.sh with PROF_SRC=1). The code is the same; made from mk0412h.sh.
# BC5 exp 0412, build g412h (2026-11-11, README section 18): g412g plus KYTY_BC5_PHYSMAP_SORTED (mksort0412.py, physmap0412.inc;
# CPU test physmap0412.cpp). Made from mk0412g.sh: kit and work directories renamed, the mksort0412.py step and its test added.
# BC5 exp 0412, build g412g (2026-11-11, README section 17): g412f plus the diagnostic KYTY_BC5_PHYSMAP_CHECK (mkphys0412.py),
# made from mk0412f.sh by renaming the kit and work directories and adding the mkphys0412.py step. The text below is g412f's:
# BC5 exp 0412, build g412f (2026-11-11, README section 15): g412e with the first fix of the host's memory bookkeeping,
# KYTY_BC5_RANGES_FAST (mkmem0412.py: VirtualRanges::QuerySpan starts at the range that holds the address instead of at
# the table's first element). Default off. On the box.
# The unit is exp 0401 e8's memory.cpp (x5-jit, ee24c888); linkmf0412.py compiles it, g412e's two event units (already
# edited, in $X/e/out) and g412d's main unit with the shared build's commands and links them with e8's other private
# objects, exp 0409's two and the shared objects. The binary is built beside g412e's and moved over it at the end;
# g412e is kept as bin/kyty_emulator.g412-<md5>. The launcher does not change. Shared files, exp0401e8, exp0409 are
# only read. CPU test first (memfast0412.cpp). BOX-LOCK by an atomic hard-link claim. No emulator is started.
# The kit (mkmem0412.py, memfast0412.cpp, linkmf0412.py, kit.sha256) is in $X/kit-f.
# usage (on the box, no emulator running): bash mk0412f.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit-i; E8=$W/exp0401e8; X9=$W/exp0409; SB=$W/kytyplus-build; LOCK=$W/BOX-LOCK
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$X/bin/kyty_emulator")" = 0167c6c0ee7d6dae75b1dc21cef59b5d ] || die "the build in place is not g412h 0167c6c0"
[ "$(m "$X/d/src/bc5LleAgc.cpp")" = 5361c8baac7690e5167e89a27cc7b4c7 ] || die "g412d's unit is not 5361c8ba"
[ "$(m "$E8/x5-jit/src/kernel/memory.cpp")" = ee24c888f976cc125502cf3a31006349 ] || die "e8's memory.cpp is not ee24c888"
[ "$(m "$X/e/out/src/kernel/eventQueue.cpp")" = 64e176a797565f1b910d575947582aa5 ] && [ "$(m "$X/e/out/src/graphics/host_gpu/renderer/sync.cpp")" = 06c1349c95f39aad41c5cf18901d4fc8 ] || die "g412e's event units are not the built ones"
[ -s "$X/kit-e/event_cap0412.hpp" ] || die "no kit-e/event_cap0412.hpp"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
LINE="guard exp 0412 | build g412i (g412h + line tables), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412i | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412i | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
B=$X/i; R=$X/raw-i
# memory.cpp includes "memoryAddressSpace.inc" from its own directory; the edited copy lives elsewhere, so e8's directory
# of that unit goes on the include path (the first build attempt stopped there).
INCK=$E8/x5-jit/src/kernel
[ -s "$INCK/memoryAddressSpace.inc" ] || die "no memoryAddressSpace.inc beside e8's memory.cpp"
mkdir -p "$B/obj" "$B/bin" "$B/out/src/kernel" "$R" || die "mkdir"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror "$K/memfast0412.cpp" -o "$R/memfast0412" < /dev/null > "$R/memfast0412-build.out" 2>&1 ||
    die "the CPU test does not build: $(grep -m2 'error' "$R/memfast0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/memfast0412" < /dev/null > "$R/memfast0412.out" 2>&1 || die "the CPU test failed: $(grep -m2 FAIL "$R/memfast0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^memfast0412: \([0-9]*\) of \1; end$' "$R/memfast0412.out" || die "no end marker from the CPU test"
echo "cpu test: $(tail -1 "$R/memfast0412.out")"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/physmap0412.cpp" -o "$R/physmap0412" < /dev/null > "$R/physmap0412-build.out" 2>&1 ||
    die "the physmap CPU test does not build: $(grep -m2 'error' "$R/physmap0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/physmap0412" < /dev/null > "$R/physmap0412.out" 2>&1 || die "the physmap CPU test failed: $(grep -m2 FAIL "$R/physmap0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^physmap0412: \([0-9]*\) of \1; end$' "$R/physmap0412.out" || die "no end marker from the physmap CPU test"
echo "cpu test: $(tail -1 "$R/physmap0412.out")"
python3 -I "$K/mkmem0412.py" "$E8/x5-jit/src/kernel/memory.cpp" "$B/out/memory-rf.cpp" > "$R/mkmem0412.out" 2> "$R/mkmem0412.err" || die "mkmem0412.py: $(tail -1 "$R/mkmem0412.err")"
cat "$R/mkmem0412.out"
python3 -I "$K/mkphys0412.py" "$B/out/memory-rf.cpp" "$B/out/memory-pc.cpp" > "$R/mkphys0412.out" 2> "$R/mkphys0412.err" || die "mkphys0412.py: $(tail -1 "$R/mkphys0412.err")"
cat "$R/mkphys0412.out"
python3 -I "$K/mksort0412.py" "$B/out/memory-pc.cpp" "$B/out/src/kernel/memory.cpp" > "$R/mksort0412.out" 2> "$R/mksort0412.err" || die "mksort0412.py: $(tail -1 "$R/mksort0412.err")"
cat "$R/mksort0412.out"
distrobox enter ubuntu -- env LC_ALL=C BC5_0412_MAIN_EXTRA=-g1 python3 -I "$K/linkmf0412.py" "$E8" "$X9/obj" "$SB" "$B/bin/kyty_emulator" "$X/d/src/bc5LleAgc.cpp" "$B/obj" "$X/kit-e:$INCK" \
    "src/kernel/memory.cpp=$B/out/src/kernel/memory.cpp" "src/kernel/eventQueue.cpp=$X/e/out/src/kernel/eventQueue.cpp" \
    "src/graphics/host_gpu/renderer/sync.cpp=$X/e/out/src/graphics/host_gpu/renderer/sync.cpp" < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED|Assertion' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:'); $(grep '^private unit' "$R/build.out" | tr '\n' ';') $(grep -m1 '^private objects' "$R/build.out")"
for s in KYTY_BC5_PHYSMAP_SORTED "tag ps412" KYTY_BC5_PHYSMAP_CHECK KYTY_BC5_RANGES_FAST KYTY_BC5_EVENT_PENDING_CAP "tag ev412" BC5_GUARD_SPLIT BC5_GUARD_CAP_ACT BC5_DIRECT_LAZY_RELEASE KYTY_BC5_EQUEUE_FIXES BC5_R3_MPROTECT_GAPS KYTY_BC5_JIT_SHM; do
  grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"
done
old=$(m "$X/bin/kyty_emulator")
if [ ! -e "$X/bin/kyty_emulator.g412-${old:0:8}" ]; then cp -p "$X/bin/kyty_emulator" "$X/bin/kyty_emulator.g412-${old:0:8}" || die "cannot keep g412h"; fi
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$X/bin/kyty_emulator.new-$$" && mv -fT "$X/bin/kyty_emulator.new-$$" "$X/bin/kyty_emulator" || die "cannot put the binary in place"
printf '%s  bin/kyty_emulator\n%s  play-pkg-0412.sh\n' "$(m "$X/bin/kyty_emulator")" "$(m "$X/play-pkg-0412.sh")" > "$X/built.md5" || die "built.md5"
echo "binary $(m "$X/bin/kyty_emulator") (g412h $old kept), launcher $(m "$X/play-pkg-0412.sh")"
echo "built: g412i"
