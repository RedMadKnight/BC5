#!/usr/bin/env bash
# BC5 exp 0421: the shared swap of "FileSystem eager" (mk0421.py, tag fs421e) on top of the shared patch PIN_OLD
# (W + games menu), the maintainer's order of 2026-11-15 (bring in the solution in place of W, check only
# that it compiles, and swap the lean and normal builds), the top session's GO. Compile only: no emulator, no GPU work.
#   1. checks: no emulator; the shared tree's diff is PIN_OLD; the kit is here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0421/swap (*.before-0421), read back
#   3. mk0421.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, only the main unit
#      changed, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned-window lines as before)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: neither binary gains or loses a switch word; lean holds no fs421e text, normal holds it
# Any failure after step 2 runs undo0421.sh (tree and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0421): PIN_OLD=<8 hex of the shared patch's md5> bash int0421.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0421/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
UNIT=$K/src/libs/bc5LleAgc.cpp
: "${PIN_OLD:?PIN_OLD=<8 hex of the shared patch md5>}"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0421 STOP: $*"; exit 1; }
undo() { echo "int0421: FAILED: $*; undoing"; bash "$HERE/undo0421.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mk0421.py ed0419g.py undo0421.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ -e "$UNIT" ] || stop "no $UNIT"
# 2
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0421: shared swap, FileSystem eager on patch $PIN_OLD; normal and lean rebuilt (CPU only, no emulator)" 30 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0421" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0421" && cp -p "$LB" "$X/kyty_emulator.lean.before-0421" && cp -p "$UNIT" "$X/bc5LleAgc.cpp.before-0421" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0421.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "UNIT=$(m8 "$UNIT")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0421"
[ "$(m8 "$X/kyty_emulator.normal.before-0421")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0421")" = "$(m8 "$LB")" ] && [ "$(m8 "$X/0001.before-0421.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0421")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0421" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 "$HERE/mk0421.py" "$K" || undo "mk0421.py refused"
git -C "$K" diff --no-color f266548 > "$X/0001-new0421.patch" || undo "cannot write the new patch"
P=$X/0001-new0421.patch; O=$X/0001.before-0421.patch
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), of them naming fs421: $(grep -c 'fs421' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0421" | cut -d= -f2)" ] || undo "the backend archive changed"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; text fs421e: $(nice -n 19 strings "$b" | grep -c 'fs421e')"
done
for v in normal lean; do
    [ -z "$(comm -3 "$X/words-$v.before" "$X/words-$v.after")" ] || undo "$v: the switch words changed"
done
[ "$(nice -n 19 strings "$LB" | grep -c 'fs421e')" = 0 ] || undo "lean holds the fs421e text"
[ "$(nice -n 19 strings "$NB" | grep -c 'fs421e')" -ge 1 ] || undo "normal lacks the fs421e text"
echo "int0421 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0421.sh"
