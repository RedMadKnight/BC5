#!/usr/bin/env bash
# BC5 exp 0412, build g412x (2026-11-12, README section 53, DESIGN-learned-windows.md): g412w plus the rule that replaces
# the learned windows, three default-off switches BC5_GUARD_MAP_RULE, BC5_GUARD_PRT_BG, BC5_GUARD_LEARN_LOG (maprule0412.inc,
# mkrule0412.py; CPU test maprule0412.cpp). Made from mk0412w.sh. The binary goes BESIDE the others: bin-x/kyty_emulator,
# built-x.md5; bin/kyty_emulator (g412v) and bin-w (g412w) are not touched.
# BC5 exp 0412, build g412w (2026-11-12, README section 48): g412v plus BC5_GUARD_ZSKIP_SCAN (zscan0412.inc, mkzscan0412.py;
# CPU test zscan0412.cpp): the zero skip takes memory back before a buffer that names it goes to the GPU. Made from mk0412v.sh.
# The binary goes BESIDE the build in place: bin-w/kyty_emulator, built-w.md5; bin/kyty_emulator (g412v) is not touched.
# BC5 exp 0412, build g412v (2026-11-12, README section 45): g412u with the poll's sample fixed (zpoll0412.inc, review R12)
# and its CPU test zpoll0412.cpp. Made from mk0412u.sh.
# BC5 exp 0412, build g412u (2026-11-11, README section 40): g412t plus BC5_GUARD_ZSKIP_POLL_SUBMIT (mkzpoll0412.py):
# the zero skip's poll before every submission. Made from mk0412t.sh.
# BC5 exp 0412, build g412t (2026-11-11, README section 39): g412s plus BC5_GUARD_NOGPU_SCAN (nscan0412.inc,
# mknscan0412.py; CPU test nscan0412.cpp): addresses in the left-out memory are found in submitted buffers and pinned. Made from mk0412s.sh.
# BC5 exp 0412, build g412s (2026-11-11, README section 37): g412r plus BC5_GUARD_NOGPU_UNPIN (nogpu0412.inc,
# mknogpu0412.py; CPU test nogpu0412.cpp): heaps the title mapped without a GPU bit are not pinned. Made from mk0412r.sh.
# BC5 exp 0412, build g412r (2026-11-11, README section 35): g412q plus the title's protection bits on the direct views
# (mkprot0412.py) and in the use catcher's table (use0412.inc). Made from mk0412q.sh.
# BC5 exp 0412, build g412q (2026-11-11, README section 33): g412p plus the zero skip's catcher BC5_GUARD_ZSKIP_STAT
# (zcat0412.inc, mkzcat0412.py). Made from mk0412p.sh.
# BC5 exp 0412, build g412p (2026-11-11, README section 32): g412o plus the use catcher BC5_GUARD_USE_STAT
# (use0412.inc, mkuse0412.py): which guest memory submitted command buffers name. Made from mk0412o.sh.
# BC5 exp 0412, build g412o (2026-11-11, README section 28): g412n plus the return-aware orphan release
# BC5_GUARD_RETURN_EXEMPT (ret0412.inc, mkret0412.py; CPU test ret0412.cpp). Made from mk0412n.sh.
# BC5 exp 0412, build g412n (2026-11-11, README section 26): g412m plus the per-buffer time line BC5_GUARD_BUF_STAT
# (buf0412.inc, mkbuf0412.py). The first build after the container's linux-libc-dev moved to 7.0.0-43: the object of the
# untouched unit memory.cpp is compared with g412m's and the result printed. Made from mk0412m.sh.
# BC5 exp 0412, build g412m (2026-11-11, README section 23): g412l plus the gap classifier BC5_GUARD_GAP_STAT (gap0412.inc,
# mkgap0412.py; its CPU test is part of lock0412.cpp). Made from mk0412l.sh.
# BC5 exp 0412, build g412l (2026-11-11, README section 22): g412k plus stage 0 of DESIGN-device-mutex.md, a line for every
# hold and wait of the device mutex of 30 ms or more (lock0412.inc). Made from mk0412k.sh.
# BC5 exp 0412, build g412k (2026-11-11, README section 21): g412j plus the parts of submit_now under the device mutex
# (mksect0412.py; lock0412.inc with mark()). Made from mk0412j.sh.
# BC5 exp 0412, build g412j (2026-11-11, README section 20): g412i plus BC5_GUARD_LOCK_STAT (mklock0412.py, lock0412.inc; CPU test
# lock0412.cpp): the device mutex counts who holds it. The main unit is edited into $B/src beside copies of g412d's .inc files.
# Made from mk0412i.sh.
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
W=$HOME/bc5-work; X=$W/exp0412; K=$X/kit-x; E8=$W/exp0401e8; X9=$W/exp0409; SB=$W/kytyplus-build; LOCK=$W/BOX-LOCK
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
(cd "$K" && sha256sum -c --quiet kit.sha256) || die "the kit is not what was sent"
[ "$(m "$X/bin/kyty_emulator")" = bc4356a5638a6486cbd23253b73cd230 ] || die "the build in place is not g412v bc4356a5"
[ "$(m "$X/d/src/bc5LleAgc.cpp")" = 5361c8baac7690e5167e89a27cc7b4c7 ] || die "g412d's unit is not 5361c8ba"
[ "$(m "$E8/x5-jit/src/kernel/memory.cpp")" = ee24c888f976cc125502cf3a31006349 ] || die "e8's memory.cpp is not ee24c888"
[ "$(m "$X/e/out/src/kernel/eventQueue.cpp")" = 64e176a797565f1b910d575947582aa5 ] && [ "$(m "$X/e/out/src/graphics/host_gpu/renderer/sync.cpp")" = 06c1349c95f39aad41c5cf18901d4fc8 ] || die "g412e's event units are not the built ones"
[ -s "$X/kit-e/event_cap0412.hpp" ] || die "no kit-e/event_cap0412.hpp"
[ "$(m "$X9/obj/libAmpr.cpp.o")" = 52c7f792a077a40749d86cde68695080 ] && [ "$(m "$X9/obj/hostMenu.cpp.o")" = 6233b8a3524656129ca71d667ca3bd2e ] || die "exp 0409's objects are not the pinned ones"
LINE="guard exp 0412 | build g412x (g412w + the map rule, the PRT background and the learn catcher, all off by default), token $$"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412-$$.new; al=$LOCK.0412-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
release() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412-rel"; mv -fT "$LOCK.0412-rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: build g412x | $(date '+%F %T')" >> "$W/BOX-QUEUE"; }
trap release EXIT
printf '%s\n' "guard exp 0412 | claimed: build g412x | $(date '+%F %T')" >> "$W/BOX-QUEUE"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the claim"
B=$X/x; R=$X/raw-x
# memory.cpp includes "memoryAddressSpace.inc" from its own directory; the edited copy lives elsewhere, so e8's directory
# of that unit goes on the include path (the first build attempt stopped there).
INCK=$E8/x5-jit/src/kernel
[ -s "$INCK/memoryAddressSpace.inc" ] || die "no memoryAddressSpace.inc beside e8's memory.cpp"
mkdir -p "$B/obj" "$B/bin" "$B/out/src/kernel" "$B/src" "$R" || die "mkdir"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread -I "$K" "$K/lock0412.cpp" -o "$R/lock0412" < /dev/null > "$R/lock0412-build.out" 2>&1 ||
    die "the lock CPU test does not build: $(grep -m2 error "$R/lock0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/lock0412" < /dev/null > "$R/lock0412.out" 2>&1 || die "the lock CPU test failed: $(grep -m2 FAIL "$R/lock0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^lock0412: \([0-9]*\) of \1; end$' "$R/lock0412.out" || die "no end marker from the lock CPU test"
echo "cpu test: $(tail -1 "$R/lock0412.out")"
cp -p "$X"/d/src/*.inc "$B/src/" || die "cannot copy the .inc files of the main unit"
python3 -I "$K/mklock0412.py" "$X/d/src/bc5LleAgc.cpp" "$B/out/bc5LleAgc-lk.cpp" > "$R/mklock0412.out" 2> "$R/mklock0412.err" || die "mklock0412.py: $(tail -1 "$R/mklock0412.err")"
cat "$R/mklock0412.out"
python3 -I "$K/mksect0412.py" "$B/out/bc5LleAgc-lk.cpp" "$B/out/bc5LleAgc-se.cpp" > "$R/mksect0412.out" 2> "$R/mksect0412.err" || die "mksect0412.py: $(tail -1 "$R/mksect0412.err")"
cat "$R/mksect0412.out"
python3 -I "$K/mkgap0412.py" "$B/out/bc5LleAgc-se.cpp" "$B/out/bc5LleAgc-gp.cpp" > "$R/mkgap0412.out" 2> "$R/mkgap0412.err" || die "mkgap0412.py: $(tail -1 "$R/mkgap0412.err")"
cat "$R/mkgap0412.out"
python3 -I "$K/mkbuf0412.py" "$B/out/bc5LleAgc-gp.cpp" "$B/out/bc5LleAgc-bf.cpp" > "$R/mkbuf0412.out" 2> "$R/mkbuf0412.err" || die "mkbuf0412.py: $(tail -1 "$R/mkbuf0412.err")"
cat "$R/mkbuf0412.out"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/ret0412.cpp" -o "$R/ret0412" < /dev/null > "$R/ret0412-build.out" 2>&1 ||
    die "the return-aware CPU test does not build: $(grep -m2 error "$R/ret0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/ret0412" < /dev/null > "$R/ret0412.out" 2>&1 || die "the return-aware CPU test failed: $(grep -m2 FAIL "$R/ret0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^ret0412: \([0-9]*\) of \1; end$' "$R/ret0412.out" || die "no end marker from the return-aware CPU test"
echo "cpu test: $(tail -1 "$R/ret0412.out")"
python3 -I "$K/mkret0412.py" "$B/out/bc5LleAgc-bf.cpp" "$B/out/bc5LleAgc-ra.cpp" > "$R/mkret0412.out" 2> "$R/mkret0412.err" || die "mkret0412.py: $(tail -1 "$R/mkret0412.err")"
cat "$R/mkret0412.out"
python3 -I "$K/mkuse0412.py" "$B/out/bc5LleAgc-ra.cpp" "$B/out/bc5LleAgc-us.cpp" > "$R/mkuse0412.out" 2> "$R/mkuse0412.err" || die "mkuse0412.py: $(tail -1 "$R/mkuse0412.err")"
cat "$R/mkuse0412.out"
python3 -I "$K/mkzcat0412.py" "$B/out/bc5LleAgc-us.cpp" "$B/out/bc5LleAgc-zc.cpp" > "$R/mkzcat0412.out" 2> "$R/mkzcat0412.err" || die "mkzcat0412.py: $(tail -1 "$R/mkzcat0412.err")"
cat "$R/mkzcat0412.out"
python3 -I "$K/mkprot0412.py" "$B/out/bc5LleAgc-zc.cpp" "$B/out/bc5LleAgc-pr.cpp" > "$R/mkprot0412.out" 2> "$R/mkprot0412.err" || die "mkprot0412.py: $(tail -1 "$R/mkprot0412.err")"
cat "$R/mkprot0412.out"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/nogpu0412.cpp" -o "$R/nogpu0412" < /dev/null > "$R/nogpu0412-build.out" 2>&1 ||
    die "the no-GPU CPU test does not build: $(grep -m2 error "$R/nogpu0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/nogpu0412" < /dev/null > "$R/nogpu0412.out" 2>&1 || die "the no-GPU CPU test failed: $(grep -m2 FAIL "$R/nogpu0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^nogpu0412: \([0-9]*\) of \1; end$' "$R/nogpu0412.out" || die "no end marker from the no-GPU CPU test"
echo "cpu test: $(tail -1 "$R/nogpu0412.out")"
python3 -I "$K/mknogpu0412.py" "$B/out/bc5LleAgc-pr.cpp" "$B/out/bc5LleAgc-ng.cpp" > "$R/mknogpu0412.out" 2> "$R/mknogpu0412.err" || die "mknogpu0412.py: $(tail -1 "$R/mknogpu0412.err")"
cat "$R/mknogpu0412.out"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/nscan0412.cpp" -o "$R/nscan0412" < /dev/null > "$R/nscan0412-build.out" 2>&1 ||
    die "the scan CPU test does not build: $(grep -m2 error "$R/nscan0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/nscan0412" < /dev/null > "$R/nscan0412.out" 2>&1 || die "the scan CPU test failed: $(grep -m2 FAIL "$R/nscan0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^nscan0412: \([0-9]*\) of \1; end$' "$R/nscan0412.out" || die "no end marker from the scan CPU test"
echo "cpu test: $(tail -1 "$R/nscan0412.out")"
python3 -I "$K/mknscan0412.py" "$B/out/bc5LleAgc-ng.cpp" "$B/out/bc5LleAgc-ns.cpp" > "$R/mknscan0412.out" 2> "$R/mknscan0412.err" || die "mknscan0412.py: $(tail -1 "$R/mknscan0412.err")"
cat "$R/mknscan0412.out"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/zpoll0412.cpp" -o "$R/zpoll0412" < /dev/null > "$R/zpoll0412-build.out" 2>&1 ||
    die "the poll CPU test does not build: $(grep -m2 error "$R/zpoll0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/zpoll0412" < /dev/null > "$R/zpoll0412.out" 2>&1 || die "the poll CPU test failed: $(grep -m2 FAIL "$R/zpoll0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^zpoll0412: \([0-9]*\) of \1; end$' "$R/zpoll0412.out" || die "no end marker from the poll CPU test"
echo "cpu test: $(tail -1 "$R/zpoll0412.out")"
python3 -I "$K/mkzpoll0412.py" "$B/out/bc5LleAgc-ns.cpp" "$B/out/bc5LleAgc-zp.cpp" > "$R/mkzpoll0412.out" 2> "$R/mkzpoll0412.err" || die "mkzpoll0412.py: $(tail -1 "$R/mkzpoll0412.err")"
cat "$R/mkzpoll0412.out"
echo "the unit before the zero-skip scan: $(m "$B/out/bc5LleAgc-zp.cpp") (g412v's was 3cea62bc; it differs by nscan0412.inc's scan() returning its completeness, review R25)"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/zscan0412.cpp" -o "$R/zscan0412" < /dev/null > "$R/zscan0412-build.out" 2>&1 ||
    die "the zero-skip scan CPU test does not build: $(grep -m2 error "$R/zscan0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/zscan0412" < /dev/null > "$R/zscan0412.out" 2>&1 || die "the zero-skip scan CPU test failed: $(grep -m2 FAIL "$R/zscan0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^zscan0412: \([0-9]*\) of \1; end$' "$R/zscan0412.out" || die "no end marker from the zero-skip scan CPU test"
echo "cpu test: $(tail -1 "$R/zscan0412.out")"
python3 -I "$K/mkzscan0412.py" "$B/out/bc5LleAgc-zp.cpp" "$B/out/bc5LleAgc-zs.cpp" > "$R/mkzscan0412.out" 2> "$R/mkzscan0412.err" || die "mkzscan0412.py: $(tail -1 "$R/mkzscan0412.err")"
cat "$R/mkzscan0412.out"
[ "$(m "$B/out/bc5LleAgc-zs.cpp")" = 1d27e927cd2da227aaefd7eaaac44b2c ] || die "the unit before the rule is not g412w's 1d27e927"
distrobox enter ubuntu -- env LC_ALL=C g++ -std=c++20 -O1 -Wall -Wextra -Werror -I "$K" "$K/maprule0412.cpp" -o "$R/maprule0412" < /dev/null > "$R/maprule0412-build.out" 2>&1 ||
    die "the map-rule CPU test does not build: $(grep -m2 error "$R/maprule0412-build.out" | cut -c1-160 | tr '\n' ' ')"
distrobox enter ubuntu -- "$R/maprule0412" < /dev/null > "$R/maprule0412.out" 2>&1 || die "the map-rule CPU test failed: $(grep -m2 FAIL "$R/maprule0412.out" | cut -c1-160 | tr '\n' ' ')"
grep -q '^maprule0412: \([0-9]*\) of \1; end$' "$R/maprule0412.out" || die "no end marker from the map-rule CPU test"
echo "cpu test: $(tail -1 "$R/maprule0412.out")"
python3 -I "$K/mkrule0412.py" "$B/out/bc5LleAgc-zs.cpp" "$B/src/bc5LleAgc.cpp" > "$R/mkrule0412.out" 2> "$R/mkrule0412.err" || die "mkrule0412.py: $(tail -1 "$R/mkrule0412.err")"
cat "$R/mkrule0412.out"
[ "$(m "$B/src/bc5LleAgc.cpp")" = 15fc40ee769dfe8e08e3cd3ab0af4bc2 ] || die "the unit with the rule is not the one checked on the laptop (15fc40ee)"
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
distrobox enter ubuntu -- env LC_ALL=C BC5_0412_MAIN_EXTRA=-g1 python3 -I "$K/linkmf0412.py" "$E8" "$X9/obj" "$SB" "$B/bin/kyty_emulator" "$B/src/bc5LleAgc.cpp" "$B/obj" "$X/kit-e:$INCK" \
    "src/kernel/memory.cpp=$B/out/src/kernel/memory.cpp" "src/kernel/eventQueue.cpp=$X/e/out/src/kernel/eventQueue.cpp" \
    "src/graphics/host_gpu/renderer/sync.cpp=$X/e/out/src/graphics/host_gpu/renderer/sync.cpp" < /dev/null > "$R/build.out" 2>&1 ||
    die "the build failed: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED|Assertion' | cut -c1-200 | tr '\n' ' ')"
[ -x "$B/bin/kyty_emulator" ] || die "no binary"
echo "untouched unit memory.cpp: this build's object $(m "$B/obj/memory.cpp.o"), g412v's $(m "$X/v/obj/memory.cpp.o") (equal = the container's header change did not reach it)"
echo "warnings: $(sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" | grep -c 'warning:'); $(grep '^private unit' "$R/build.out" | tr '\n' ';') $(grep -m1 '^private objects' "$R/build.out")"
for s in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG "tag mr412" BC5_GUARD_ZSKIP_SCAN "tag zs412" BC5_GUARD_ZSKIP_POLL_SUBMIT "tag zp412" BC5_GUARD_NOGPU_SCAN "tag ns412" BC5_GUARD_NOGPU_UNPIN "tag ng412" "protection bits" BC5_GUARD_ZSKIP_STAT "tag zc412" BC5_GUARD_USE_STAT "tag us412" BC5_GUARD_RETURN_EXEMPT "tag ra412" BC5_GUARD_BUF_STAT BC5_GUARD_GAP_STAT "tag gp412" "lock hold" "lock wait" "lock parts" BC5_GUARD_LOCK_STAT "tag lk412" KYTY_BC5_PHYSMAP_SORTED "tag ps412" KYTY_BC5_PHYSMAP_CHECK KYTY_BC5_RANGES_FAST KYTY_BC5_EVENT_PENDING_CAP "tag ev412" BC5_GUARD_SPLIT BC5_GUARD_CAP_ACT BC5_DIRECT_LAZY_RELEASE KYTY_BC5_EQUEUE_FIXES BC5_R3_MPROTECT_GAPS KYTY_BC5_JIT_SHM; do
  grep -aqF -- "$s" "$B/bin/kyty_emulator" || die "the binary lacks [$s]"
done
# BESIDE the build in place (his shortcut's binary stays byte-identical): bin-x/kyty_emulator.
mkdir -p "$X/bin-x" || die "mkdir bin-x"
pgrep '^kyty_emulator' > /dev/null && die "an emulator started during the build; nothing put in place"
cp -p "$B/bin/kyty_emulator" "$X/bin-x/kyty_emulator.new-$$" && mv -fT "$X/bin-x/kyty_emulator.new-$$" "$X/bin-x/kyty_emulator" || die "cannot put the binary beside"
printf '%s  bin-x/kyty_emulator\n' "$(m "$X/bin-x/kyty_emulator")" > "$X/built-x.md5" || die "built-x.md5"
[ "$(m "$X/bin/kyty_emulator")" = bc4356a5638a6486cbd23253b73cd230 ] || die "the build in place changed"
echo "binary beside $(m "$X/bin-x/kyty_emulator") (bin-x); the build in place $(m "$X/bin/kyty_emulator") untouched"
echo "built: g412x"
