#!/usr/bin/env bash
# BC5 exp 0412, the lean build g412L (2026-11-12, README section 43), BESIDE the build in place (bin-lean/kyty_emulator):
#   - the main unit is g412d's (5361c8ba) plus ONLY the zero skip's poll before every submission (mkzpolll0412.py): none of
#     the catchers and counters of g412j..g412t are compiled in (lock, sections, gaps, buffers, return-aware release, use,
#     zero-skip catcher, protection bits, no-GPU unpin and scan);
#   - the three private units and the main unit are compiled with -DBC5_LEAN=1 (exp 0177: no journal, traces, tallies,
#     frame profile; the diagnostic switches read as unset) and without -g1;
#   - memory.cpp keeps mkmem, mkphys (its check stays a switch that is off; mksort0412.py pins that input) and mksort.
# e8's other 47 private objects and the shared objects are the normal ones (not rebuilt lean). bin/kyty_emulator is not touched.
# usage (on the box, no emulator running): bash mk0412L.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit-L; E8=$W/exp0401e8; X9=$W/exp0409; SB=$W/kytyplus-build; LOCK=$W/BOX-LOCK
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$X/d/src/bc5LleAgc.cpp")" = 5361c8baac7690e5167e89a27cc7b4c7 ] || die "g412d's unit is not 5361c8ba"
[ "$(m "$E8/x5-jit/src/kernel/memory.cpp")" = ee24c888f976cc125502cf3a31006349 ] || die "e8's memory.cpp is not ee24c888"
[ "$(m "$X/e/out/src/kernel/eventQueue.cpp")" = 64e176a797565f1b910d575947582aa5 ] && [ "$(m "$X/e/out/src/graphics/host_gpu/renderer/sync.cpp")" = 06c1349c95f39aad41c5cf18901d4fc8 ] || die "g412e's event units are not the built ones"
[ -s "$X/kit-e/event_cap0412.hpp" ] || die "no kit-e/event_cap0412.hpp"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
LINE="guard exp 0412 | build g412L (lean, beside), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412L | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412L | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
B=$X/L; R=$X/raw-L
# memory.cpp includes "memoryAddressSpace.inc" from its own directory; the edited copy lives elsewhere, so e8's directory
# of that unit goes on the include path (the first build attempt stopped there).
INCK=$E8/x5-jit/src/kernel
[ -s "$INCK/memoryAddressSpace.inc" ] || die "no memoryAddressSpace.inc beside e8's memory.cpp"
mkdir -p "$B/obj" "$B/bin" "$B/out/src/kernel" "$B/src" "$R" || die "mkdir"
cp -p "$X"/d/src/*.inc "$B/src/" || die "cannot copy the .inc files of the main unit"
python3 -I "$K/mkzpolll0412.py" "$X/d/src/bc5LleAgc.cpp" "$B/src/bc5LleAgc.cpp" > "$R/mkzpolll0412.out" 2> "$R/mkzpolll0412.err" || die "mkzpolll0412.py: $(tail -1 "$R/mkzpolll0412.err")"
cat "$R/mkzpolll0412.out"
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
distrobox enter ubuntu -- env LC_ALL=C BC5_0412_MAIN_EXTRA=-DBC5_LEAN=1 BC5_0412_PAIR_EXTRA=-DBC5_LEAN=1 python3 -I "$K/linkmf0412l.py" "$E8" "$X9/obj" "$SB" "$B/bin/kyty_emulator" "$B/src/bc5LleAgc.cpp" "$B/obj" "$X/kit-e:$INCK" \
    "src/kernel/memory.cpp=$B/out/src/kernel/memory.cpp" "src/kernel/eventQueue.cpp=$X/e/out/src/kernel/eventQueue.cpp" \
    "src/graphics/host_gpu/renderer/sync.cpp=$X/e/out/src/graphics/host_gpu/renderer/sync.cpp" < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED|Assertion' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:'); $(grep '^private unit' "$R/build.out" | tr '\n' ';') $(grep -m1 '^private objects' "$R/build.out")"
for s in BC5_GUARD_ZSKIP_POLL_SUBMIT KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_RANGES_FAST KYTY_BC5_EVENT_PENDING_CAP BC5_GUARD_SPLIT BC5_DIRECT_LAZY_RELEASE BC5_DIRECT_ZERO_SKIP KYTY_BC5_EQUEUE_FIXES BC5_R3_MPROTECT_GAPS KYTY_BC5_JIT_SHM; do
  grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"
done
for s in BC5_GUARD_LOCK_STAT BC5_GUARD_GAP_STAT BC5_GUARD_BUF_STAT BC5_GUARD_USE_STAT BC5_GUARD_ZSKIP_STAT BC5_GUARD_NOGPU_UNPIN BC5_GUARD_NOGPU_SCAN BC5_GUARD_RETURN_EXEMPT; do
  grep -aqF -- "$s" "$B/bin/kyty_emulator" && die "the lean binary still has [$s]"
done
mkdir -p "$X/bin-lean" || die "mkdir bin-lean"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$X/bin-lean/kyty_emulator.new-$$" && mv -fT "$X/bin-lean/kyty_emulator.new-$$" "$X/bin-lean/kyty_emulator" || die "cannot put the lean binary in place"
echo "lean binary $(m "$X/bin-lean/kyty_emulator") ($(stat -c %s "$X/bin-lean/kyty_emulator") bytes; the build in place $(m "$X/bin/kyty_emulator"), $(stat -c %s "$X/bin/kyty_emulator") bytes, untouched)"
echo "built: g412L"
