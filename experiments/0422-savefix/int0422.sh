#!/usr/bin/env bash
# BC5 exp 0422: the shared swap of exp 0417's transferring-mount save fix made fixed (mk0422.py, tag sdt422) on top of
# the shared patch PIN_OLD (e3fd8b55: W + games menu + exp 0421), the maintainer's word of 2026-11-15 (the save fix is to be
# on for good, in the code, to the top session), the top session's GO. Made from int0421.sh.
#   1. checks: no emulator; the shared tree's diff is PIN_OLD; the kit is here
#   2. the lock (chain_claim, one line, unless a chain passes CHAIN_LOCKLINE); copies under ~/bc5-work/exp0422/swap
#      (*.before-0422), read back
#   3. mk0422.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the same file list,
#      BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned-window lines as before, no KYTY_BC5_SAVEDATA_TRANSFER_FIX)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: normal loses exactly the word KYTY_BC5_SAVEDATA_TRANSFER_FIX and gains none; lean gains and loses
#      none; normal holds the "sdt417: transferring mount" text, lean holds none
# Any failure after step 2 runs undo0422.sh (tree and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0422): PIN_OLD=<8 hex of the shared patch's md5> bash int0422.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0422/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
UNIT=$K/src/libs/libSaveData.cpp
GONE=KYTY_BC5_SAVEDATA_TRANSFER_FIX
: "${PIN_OLD:?PIN_OLD=<8 hex of the shared patch md5>}"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0422 STOP: $*"; exit 1; }
undo() { echo "int0422: FAILED: $*; undoing"; bash "$HERE/undo0422.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mk0422.py ed0419g.py undo0422.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ -e "$UNIT" ] || stop "no $UNIT"
# 2
. "$N/chainlock0417.inc"
if [ -n "${CHAIN_LOCKLINE:-}" ]; then
    [ "$(cat "$W/BOX-LOCK")" = "$CHAIN_LOCKLINE" ] || stop "the chain's lock line is not in BOX-LOCK"
    trap - EXIT
else
    chain_claim "exp 0422: shared swap, the save fix fixed on patch $PIN_OLD; normal and lean rebuilt (CPU only, no emulator)" 30 || stop "no lock"
    trap chain_release EXIT
fi
[ -e "$X/kyty_emulator.normal.before-0422" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0422" && cp -p "$LB" "$X/kyty_emulator.lean.before-0422" && cp -p "$UNIT" "$X/libSaveData.cpp.before-0422" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0422.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "UNIT=$(m8 "$UNIT")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0422"
[ "$(m8 "$X/kyty_emulator.normal.before-0422")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0422")" = "$(m8 "$LB")" ] && [ "$(m8 "$X/0001.before-0422.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0422")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0422" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 "$HERE/mk0422.py" "$K" || undo "mk0422.py refused"
git -C "$K" diff --no-color f266548 > "$X/0001-new0422.patch" || undo "cannot write the new patch"
P=$X/0001-new0422.patch; O=$X/0001.before-0422.patch
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
[ "$(grep -c "$GONE" "$P")" = 0 ] || undo "the patch still names $GONE"
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), of them in libSaveData: $(grep -c 'libSaveData.*warning' "$X/build-$v.log"); compiled: $(grep -c 'libSaveData.cpp.o' "$X/build-$v.log") step(s) on libSaveData"
done
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0422" | cut -d= -f2)" ] || undo "the backend archive changed"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; text 'sdt417: transferring mount': $(nice -n 19 strings "$b" | grep -c 'sdt417: transferring mount'), 'transferring mount fix': $(nice -n 19 strings "$b" | grep -c 'transferring mount fix')"
done
[ "$(comm -3 "$X/words-normal.before" "$X/words-normal.after" | tr -d ' \t')" = "$GONE" ] || undo "normal: the switch words changed other than -$GONE"
[ -z "$(comm -3 "$X/words-lean.before" "$X/words-lean.after")" ] || undo "lean: the switch words changed"
[ "$(nice -n 19 strings "$LB" | grep -c 'sdt417')" = 0 ] || undo "lean holds sdt417 text"
[ "$(nice -n 19 strings "$NB" | grep -c 'sdt417: transferring mount')" -ge 1 ] || undo "normal lacks the sdt417 text"
[ "$(nice -n 19 strings "$NB" "$LB" | grep -c 'transferring mount fix')" = 0 ] || undo "a binary still holds the switch's report line"
echo "int0422 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0422.sh"
