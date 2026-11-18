#!/usr/bin/env bash
# BC5 exp 0430, the swap of the hang fix BUILT IN (2026-11-18 evening; the maintainer: "Wprowadzamy wszystkie 4 poprawki.
# Usuń przełączniki i wybuduj w kod. Przygotuj czysta wersję lean i zwykłego buildu."). Run by the top session after it has
# verified the tests (the order: this session does not swap). Only src/libs/bc5LleAgc.cpp changes (mkbake0430.py with
# ho430.bake.cpp and ho430.b8.cpp beside this script); the backend archive is the same (F4's add_next_submit_dependency is
# in it since the first exp 0430 swap) and is checked to stay so.
#   1. checks: no emulator; the shared tree's diff is ef2ff54f; normal a9b4f00b, lean abf5fb17; the unit f574f460; the
#      archive 6eac453e; the kit here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0430/swapb (*.before-0430b), read back; pins file
#   3. mkbake0430.py on ~/src/KytyPlus; the unit must be UNIT_NEW; the new patch = git diff f266548 must be PATCH_NEW;
#      checks on it (exp 0372 = 5, the pad_audio_route header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG /
#      learned / JOB_ARENA line counts as before)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the archive must stay the same
#   5. strings: normal loses exactly the three XQ words, lean those and KYTY_BC5_ANON_SYNC_KICK; neither gains a word
# Any failure after step 2 runs undo0430b.sh (the unit and both binaries back, checked by md5).
# usage (on the box, in the kit directory): bash int0430b.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0430/swapb
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
U1=$K/src/libs/bc5LleAgc.cpp
PIN_OLD=ef2ff54f; NORMAL_OLD=a9b4f00b; LEAN_OLD=abf5fb17; U1_OLD=f574f460; ARCH_OLD=6eac453e
UNIT_NEW=8eb42a10; PATCH_NEW=d1388db0
LOST_N="BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_FENCE BC5_DIRECT_XQ_PENDING"
LOST_L="BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_FENCE BC5_DIRECT_XQ_PENDING KYTY_BC5_ANON_SYNC_KICK"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0430b STOP: $*"; exit 1; }
undo() { echo "int0430b: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0430b.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkbake0430.py ho430.bake.cpp ho430.b8.cpp undo0430b.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$U1")" = "$U1_OLD" ] || stop "the unit is $(m8 "$U1"), not $U1_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0430: shared swap, the hang fix built in (F10 + F4 + F16 + F18, no switch), patch $PIN_OLD -> $PATCH_NEW; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0430b" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0430b" && cp -p "$LB" "$X/kyty_emulator.lean.before-0430b" \
  && cp -p "$U1" "$X/bc5LleAgc.cpp.before-0430b" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0430b.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0430b"
[ "$(m8 "$X/kyty_emulator.normal.before-0430b")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0430b")" = "$LEAN_OLD" ] \
  && [ "$(m8 "$X/bc5LleAgc.cpp.before-0430b")" = "$U1_OLD" ] && [ "$(m8 "$X/0001.before-0430b.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0430b")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0430b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkbake0430.py" "$K" || undo "mkbake0430.py refused"
[ "$(m8 "$U1")" = "$UNIT_NEW" ] || undo "the edited unit is $(m8 "$U1"), not $UNIT_NEW"
git -C "$K" diff --no-color f266548 > "$X/0001-new0430b.patch" || undo "cannot write the new patch"
P=$X/0001-new0430b.patch; O=$X/0001.before-0430b.patch
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
echo "the patch: $(m8 "$O") -> $(m8 "$P"), $(diff "$O" "$P" | grep -c '^[<>]') lines differ, exp 0372 lines 5, pad_audio_route header in"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), of them in bc5LleAgc.cpp: $(grep -c 'bc5LleAgc.cpp.*warning' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || undo "the archive changed: $(m8 "$ARCH")"
# 5
for v in normal lean; do
    b=$NB; want=$LOST_N; [ $v = lean ] && { b=$LB; want=$LOST_L; }
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ -z "$gained" ] || undo "$v: words gained: $gained"
    [ "$lost" = "$want" ] || undo "$v: the words lost are [$lost], not [$want]"
done
nice -n 19 strings "$LB" | grep -qF "THE BOUND STANDS" && undo "lean: the fix's counting is in the binary"
nice -n 19 strings "$NB" | grep -qF "THE BOUND STANDS" || undo "normal: the fix's counting is not in the binary"
echo "int0430b done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0430b.sh (to $PIN_OLD; further back: exp 0429's undo0429r.sh)"
