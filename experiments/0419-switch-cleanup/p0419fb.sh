#!/usr/bin/env bash
# BC5 exp 0413, the PRIVATE build of the integration (the top session's GO, 2026-11-12 10:56, slot to 12:30): patch 0001
# 76c1d045 (branch int/0413-tested-into-shared) built under ~/bc5-work/exp0413/p only. ~/src/KytyPlus, the shared build
# directories, the backend source and the backend archive are only read.
#   1. checks: no emulator, the shared tree's diff is 0001-old (2dbed49a), the kit's md5s, the archive's md5
#   2. the lock; the shared tree copied without .git; 0001-old reversed and 0001-new applied; every patched file checked
#      against tree.md5 (made from the laptop's replay tree)
#   3. configure and build normal and lean (bc5-build.sh's options, the shared backend paths), nice 19
#   4. checks on the binaries; the archive unchanged; the lock released
# p0419f (exp 0419, candidate F): the private tree goes from 0001-new18 (410273ca, E) to 0001-new19 (P_NEW19); the
# private backend is made again from the same two files. usage: P_NEW19=<patch md5> bash p0419f.sh
# p0419e (exp 0419, candidate E): the private tree goes from 0001-new15 (1689b7da) to 0001-new18 (P_NEW17); the private
# backend gets exp 0412's two files WITHOUT the probe. usage: P_NEW17=<patch md5> bash p0419e.sh
# p0417c (exp 0417, the K1r fold): the private tree goes from 0001-new11 (c55174b1) to 0001-new12 (P_NEW12); a PRIVATE
# backend archive is built from a copy of the shared source with exp 0412's two files, and both emulator builds are
# configured against it. usage: P_NEW12=<patch md5> bash p0417c.sh
# p0417b (exp 0417, the next patch change): the private tree goes from 0001-new10 (33bddfa1) to 0001-new11
# (P_NEW11); normal and lean; the set-buffer test hook must be absent. usage: P_NEW11=<patch md5> bash p0417b.sh
# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412): the private tree goes from 0001-new8 (a099e662) to
# 0001-new9 (P_NEW9); the marks are the three experiments' switches. usage: P_NEW9=<patch md5> bash p0416c.sh
# p0413b (the top, 2026-11-12 12:0x): incremental: the private tree keeps its build dirs; 0001-new (76c1d045) is reversed
# and 0001-new2 applied, so ninja rebuilds only what changed. usage: bash p0413b.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0413; P=$E/p; HERE=$(cd "$(dirname "$0")" && pwd); K=$HOME/src/KytyPlus
LOCK=$W/BOX-LOCK; ID=$E/lock.line; ARCH=$W/backend-ubuntu/libbc5_backend.a; BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "p0413 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0413-$$.new a=$LOCK.0413-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    mkdir -p "$E" || stop "cannot make $E"
    if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then  # exp 0417: the chain's one lock line
        printf '%s\n' "$CHAIN_LOCKLINE" > "$ID" || stop "cannot record the line"; INHERIT=1; echo "claimed: inherited from the chain: $CHAIN_LOCKLINE"; return 0
    fi
    line="exp 0413 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
    mkdir "$c" 2> /dev/null || stop "another claim runs, or $c was left behind"
    fail() { rm -f "$t"; rmdir "$c"; stop "$1"; }
    printf '%s\n' "$line" > "$t" || fail "cannot write $t"
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        { [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; } && fail "$LOCK is not a plain file"
        [ -s "$LOCK" ] && fail "foreign lock: $(cat "$LOCK")"
        mv -T "$LOCK" "$a" || fail "the lock moved under us"
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        [ -s "$a" ] || rm -f "$a"
        fail "lost the claim to: $(cat "$LOCK" 2> /dev/null)"
    fi
    if [ -s "$a" ]; then
        local w; w=$(cat "$a"); mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim: $w"
    fi
    rm -f "$a" "$t"; rmdir "$c" || stop "cannot remove $c"
    printf '%s\n' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"
    own || stop "the lock does not read back as ours"
    echo "claimed: $line"
}
release() {
    if [ "${INHERIT:-0}" = 1 ]; then rm -f "$ID"; echo "lock released (kept by the chain)"; return 0; fi
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "p0413: the lock could not be released"; return 1; fi
    echo "p0413: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
die() { echo "p0413 STOP: $*"; release; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 27b6416f ] || stop "the shared tree is not 0001 27b6416f"
[ "$(m "$HERE/0001-new18.patch")" = d9af28ca ] && [ "$(m "$HERE/0001-new19.patch")" = "${P_NEW19:?the new patch md5}" ] || stop "the kit's patches are not the pins"
[ "$(m "$ARCH")" = 75e30335 ] || stop "the archive is not 75e30335"
[ -d "$BSRC/include/bc5" ] || stop "no backend include dir at $BSRC"
claim "exp 0419: private rebuild back to candidate F from the diagnostic build (tree and a private backend) under exp0413/p, CPU only" 40
echo "$(date '+%F %T') start; archive $(m "$ARCH")"
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs before: $f"; bad=$((bad + 1)); }; done < "$HERE/tree19.md5"
[ "$bad" = 0 ] || die "$bad files of the private tree are not the diagnostic build.s (e794fbe6)"
(cd "$P/tree" && git apply -R --whitespace=nowarn "$HERE/0001-new19.patch" && git apply --whitespace=nowarn "$HERE/0001-new18.patch") || die "reapplying"
bad=0
while read -r sum f; do [ "$(md5sum < "$P/tree/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree18.md5"
[ "$bad" = 0 ] || die "$bad files differ from the laptop's tree"
echo "tree: $(wc -l < "$HERE/tree18.md5") patched files match the laptop's (0001-new18, back to F)"
# exp 0417 (the K1r fold): the PRIVATE backend. The shared source copied, exp 0412's two files put in, its own build dir.
PB=$P/backend-src; BB=$P/backend-build; BT=$P/backend-test
[ "$(m "$BSRC/include/bc5/direct.hpp")" = a9fcb26b ] && [ "$(m "$BSRC/src/direct.cpp")" = 51279eae ] || die "the shared backend source is not a9fcb26b / 51279eae"
[ "$(m "$HERE/backend-direct-noprobe.hpp")" = e96e5c73 ] && [ "$(m "$HERE/backend-direct-noprobe.cpp")" = 28100ce5 ] || die "the kit's backend files are not e96e5c73 / 28100ce5"
rm -rf "$PB" "$BB" "$BT" && cp -a "$BSRC" "$PB" || die "cannot copy the backend source"
cp "$HERE/backend-direct-noprobe.hpp" "$PB/include/bc5/direct.hpp" && cp "$HERE/backend-direct-noprobe.cpp" "$PB/src/direct.cpp" || die "cannot put the two backend files in"
[ "$(diff -rq "$BSRC" "$PB" | grep -c .)" = 2 ] || die "the private backend differs from the shared one by more than direct.hpp and direct.cpp: $(diff -rq "$BSRC" "$PB" | head -4 | tr '\n' ' ')"
# The recipe checked first (exp 0412's author: it was never shown that these options reproduce the shared archive):
# the UNTOUCHED shared source built the same way, its archive compared with the shared one. Informational.
BR=$P/backend-ref
rm -rf "$BR"
if distrobox enter ubuntu -- cmake -S "$BSRC" -B "$BR" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
       -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BR.configure.log" 2>&1 &&
   distrobox enter ubuntu -- sh -c "cd '$BR' && nice -n 19 ninja" < /dev/null > "$BR.build.log" 2>&1 && [ -f "$BR/libbc5_backend.a" ]; then
    echo "recipe check: the untouched shared backend source built with these options gives $(m "$BR/libbc5_backend.a"); the shared archive is $(m "$ARCH") ($([ "$(m "$BR/libbc5_backend.a")" = "$(m "$ARCH")" ] && echo "the SAME: a rebuild reproduces it" || echo "DIFFERENT: a rollback must restore the kept archive file, not rebuild"))"
else
    echo "recipe check: the untouched shared backend source did not build with these options ($(grep -m1 -i error "$BR.configure.log" "$BR.build.log" 2> /dev/null | cut -c1-160))"
fi
echo "== $(date +%T) backend"
distrobox enter ubuntu -- cmake -S "$PB" -B "$BB" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BB.configure.log" 2>&1 || die "backend configure: $(tail -3 "$BB.configure.log" | tr '\n' ' ' | cut -c1-300)"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja" < /dev/null > "$BB.build.log" 2>&1 || { grep -m6 -E "error:" "$BB.build.log" | cut -c1-240; die "the backend build failed"; }
[ -f "$BB/libbc5_backend.a" ] || die "no private backend archive"
echo "private backend archive $(md5sum < "$BB/libbc5_backend.a" | cut -d' ' -f1) (the shared one $(m "$ARCH") untouched; exp 0412's with the probe was ed63df2f; this one has no probe)"
# the backend's own tests on the private copy (CPU only; they never submit: CLAUDE.md hard rule 5). A container that
# cannot build them is reported, not fatal.
if distrobox enter ubuntu -- cmake -S "$PB" -B "$BT" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
       -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON < /dev/null > "$BT.configure.log" 2>&1 &&
   distrobox enter ubuntu -- sh -c "cd '$BT' && nice -n 19 ninja" < /dev/null > "$BT.build.log" 2>&1; then
    if distrobox enter ubuntu -- sh -c "cd '$BT' && ctest --output-on-failure" < /dev/null > "$BT.ctest.log" 2>&1; then echo "backend tests: PASS: $(grep -m1 'tests passed' "$BT.ctest.log" | cut -c1-120)"
    else echo "backend tests: FAILED: $(grep -m3 -i 'failed\|\*\*\*' "$BT.ctest.log" | tr '\n' ' ' | cut -c1-300)"; die "the backend's tests failed on the private copy"; fi
else
    echo "backend tests: NOT RUN (the test build did not configure or compile here: $(grep -m2 -i 'error' "$BT.configure.log" "$BT.build.log" 2> /dev/null | tr '\n' ' ' | cut -c1-240))"
fi
BSRC=$PB; BBLD=$BB   # both emulator builds are configured against the private backend below
cfg() {  # build dir, extra -D
    distrobox enter ubuntu -- cmake -S "$P/tree" -B "$1" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF \
        -DKYTY_BC5_BACKEND_SRC="$BSRC" -DKYTY_BC5_BACKEND_BUILD="$BBLD" $2 < /dev/null > "$1.configure.log" 2>&1
}
for v in normal lean; do
    pgrep '^kyty_emulator' > /dev/null && die "an emulator started; stopped before $v"
    d=$P/build-$v; x=""; [ $v = lean ] && x="-DKYTY_BC5_LEAN=ON"
    [ -f "$d/build.ninja" ] || die "no build dir $d (run p0413.sh first)"
    cfg "$d" "$x" || die "configure $v against the private backend: $(tail -2 "$d.configure.log" | tr '\n' ' ' | cut -c1-240)"
    echo "== $(date +%T) build $v"
    distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1 || { grep -m5 -E "error:" "$d.build.log"; die "build $v"; }
    b=$d/src/kyty_emulator
    [ -x "$b" ] || die "no binary for $v"
    echo "$v: $(md5sum < "$b" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log")"
    for s in "NpCppWebApi SessionManager V2 on (10 exports registered)" KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_AMM_SETBUFFER_MAP KYTY_BC5_EVENT_COALESCE_SAME KYTY_BC5_SEMA_TARGETED_WAKE KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_FW_NET KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT BC5_GUARD_K1R BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG KYTY_BC5_MAP_RECORDS KYTY_BC5_AMM_SCATTER BC5_GUARD_K1_FILTER BC5_GUARD_LAZY_BY_DATA KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_MEMORY_LOG KYTY_BC5_SAVEDATA_TRANSFER_FIX BC5_GUARD_WRITERS BC5_DIRECT_START_STATE_SKIP; do
        grep -aqF -- "$s" "$b" || die "$v lacks [$s]"
    done
    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"
    for s in BC5_GUARD_K1R_PROBE KYTY_BC5_NAMES_FAST KYTY_BC5_MIN_FLIP_RATE BC5_GUARD_ZSKIP_POLL_SUBMIT BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_GC_HS_OFFCHIP; do   # exp 0419: no probe; removed options
        grep -aqF -- "$s" "$b" && die "$v holds [$s]"
    done
    for n in eVU3cXIJz0w BY1jyWLZrcA JiY4sfHkV34 LbhH9NeB93I XuVY56j7GM0 fIzsqjyD5oY sRn6qePT54Q -0Vv7HKZaBM yl3T9brJay4 xjVhrq2KPJA; do
        strings "$b" | grep -qx -- "$n" || die "$v lacks the NID $n"
    done
done
[ "$(m "$ARCH")" = 75e30335 ] || die "the archive changed"
echo "$(date '+%F %T') done; normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"
release
