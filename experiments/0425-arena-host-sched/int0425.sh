#!/usr/bin/env bash
# BC5 exp 0425: the shared swap of C1 (the 200 us wake slice), on by default for every title (mkc1.py), on top of the
# shared patch 4945ef1b; the maintainer's word of 2026-11-16 to the top session (for now this solution goes into all versions,
# to be withdrawn later if need be), the top session's GO. Made from exp 0422's int0422.sh.
#   1. checks: no emulator; the shared tree's diff is 4945ef1b; both binaries are 9da2a9d5 / f942676c; the kit is here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0425/swap (*.before-0425), read back
#   3. mkc1.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the pad_audio_route
#      header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned-window lines as before, no catcher,
#      C2, C3 or PlayGo words)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds gain exactly the word KYTY_BC5_0425_WAKE_SLICE_US and lose none; normal holds the
#      "C1 wake slice" line, lean no "exp 0425" text
# Any failure after step 2 runs undo0425.sh (the two units and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0425): bash int0425.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0425/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
U1=$K/src/kernel/pthread.cpp; U2=$K/src/bc5/switch_defaults.hpp
PIN_OLD=4945ef1b; NORMAL_OLD=9da2a9d5; LEAN_OLD=f942676c
NEW=KYTY_BC5_0425_WAKE_SLICE_US
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0425 STOP: $*"; exit 1; }
undo() { echo "int0425: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0425.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkc1.py patch0425.py undo0425.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0425: shared swap, C1 (wake slice 200 us) on by default, patch $PIN_OLD + C1; normal and lean rebuilt (CPU only, no emulator)" 30 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0425" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0425" && cp -p "$LB" "$X/kyty_emulator.lean.before-0425" \
  && cp -p "$U1" "$X/pthread.cpp.before-0425" && cp -p "$U2" "$X/switch_defaults.hpp.before-0425" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0425.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "U2=$(m8 "$U2")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0425"
[ "$(m8 "$X/kyty_emulator.normal.before-0425")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0425")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/0001.before-0425.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0425")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0425" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 "$HERE/mkc1.py" "$K" || undo "mkc1.py refused"
git -C "$K" diff --no-color f266548 > "$X/0001-new0425.patch" || undo "cannot write the new patch"
P=$X/0001-new0425.patch; O=$X/0001.before-0425.patch
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
for w in KYTY_BC5_0425_CATCH KYTY_BC5_0425_HANDOFF_US KYTY_BC5_0425_DIRECT_WAKE KYTY_BC5_0425_PLAYGO; do
    [ "$(grep -c "$w" "$P")" = 0 ] || undo "the patch names $w"
done
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5, pad_audio_route header in"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), of them in pthread.cpp: $(grep -c 'pthread.cpp.*warning' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0425" | cut -d= -f2)" ] || undo "the backend archive changed"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'C1 wake slice': $(nice -n 19 strings "$b" | grep -c 'C1 wake slice'), 'exp 0425': $(nice -n 19 strings "$b" | grep -c 'exp 0425')"
done
for v in normal lean; do
    [ "$(comm -3 "$X/words-$v.before" "$X/words-$v.after" | tr -d ' \t')" = "$NEW" ] || undo "$v: the switch words changed other than +$NEW"
done
[ "$(nice -n 19 strings "$LB" | grep -c 'exp 0425')" = 0 ] || undo "lean holds exp 0425 text"
[ "$(nice -n 19 strings "$NB" | grep -c 'C1 wake slice')" -ge 1 ] || undo "normal lacks the C1 line"
echo "int0425 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0425.sh"
