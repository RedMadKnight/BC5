#!/usr/bin/env bash
# BC5 exp 0429, the shared swap of R (int0429.sh's pattern): candidate R on by default for every title and exp 0425's
# wake slice removed (mkswap0429r.py, its swap form: no stressor, no slice), on top of the shared patch 940e8f36 (exp
# 0432's build 5). The maintainer's word, 2026-11-18 ("Wlaczyc R domyslnie we wspolnych buildach => tak, od razu posprzataj
# inne rzeczy, ktore po wprowadzeniu R staja sie zbedne"), through the top session.
#   1. checks: no emulator; the shared tree's diff is 940e8f36; normal 4e0c00a2, lean 272685ee, archive 6eac453e; the
#      three units at their pins (pins-swap0429r.txt); kit here
#   2. the lock (chain_claim); copies under ~/bc5-work/exp0429/swapR (*.before-0429r), read back; pins file
#   3. mkswap0429r.py on ~/src/KytyPlus; the new patch = git diff f266548; checks: it is the laptop's ef2ff54f, exp 0372
#      lines 5, the pad_audio_route header in, the file list unchanged, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned
#      line counts unchanged, WAKE_SLICE 0 lines
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: each build gains KYTY_BC5_0429_RR and loses KYTY_BC5_0425_WAKE_SLICE_US, nothing else; the lean build
#      holds no "exp 0429" or "exp 0425" text (no diagnostics), the normal one no "exp 0425"
# Any failure after step 2 runs undo0429r.sh (units and binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0429): bash int0429r.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0429/swapR
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
PIN_OLD=940e8f36; NORMAL_OLD=4e0c00a2; LEAN_OLD=272685ee; ARCH_OLD=6eac453e; PIN_NEW=ef2ff54f
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0429r STOP: $*"; exit 1; }
undo() { echo "int0429r: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0429r.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkswap0429r.py rrshared0429.cpp pins-swap0429r.txt undo0429r.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
while read -r h u; do [ "$(md5sum < "$K/$u" | cut -d' ' -f1)" = "$h" ] || stop "$u is not its pin"; done < "$HERE/pins-swap0429r.txt"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0429: shared swap, R on by default and the wake slice removed, patch $PIN_OLD + 0429 R; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/pins.before-0429r" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0429r" && cp -p "$LB" "$X/kyty_emulator.lean.before-0429r" || stop "cannot copy"
while read -r h u; do cp -p "$K/$u" "$X/units/$(basename "$u").before-0429r" || stop "cannot copy $u"; done < "$HERE/pins-swap0429r.txt"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0429r.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"
  while read -r h u; do echo "UNIT ${h:0:8} $u"; done < "$HERE/pins-swap0429r.txt"; } > "$X/pins.before-0429r"
[ "$(m8 "$X/kyty_emulator.normal.before-0429r")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0429r")" = "$LEAN_OLD" ] \
  && [ "$(m8 "$X/0001.before-0429r.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
while read -r h u; do [ "$(md5sum < "$X/units/$(basename "$u").before-0429r" | cut -d' ' -f1)" = "$h" ] || stop "the copy of $u does not read back"; done < "$HERE/pins-swap0429r.txt"
echo "before: $(grep -v '^UNIT' "$X/pins.before-0429r" | tr '\n' ' ')"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0429r" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkswap0429r.py" "$K" || undo "mkswap0429r.py refused"
git -C "$K" diff --no-color f266548 > "$X/0001-new0429r.patch" || undo "cannot write the new patch"
P=$X/0001-new0429r.patch; O=$X/0001.before-0429r.patch
[ "$(m8 "$P")" = "$PIN_NEW" ] || undo "the new patch is $(m8 "$P"), not $PIN_NEW (the laptop's)"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
[ "$(grep '^diff --git ' "$O" | md5sum)" = "$(grep '^diff --git ' "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
[ "$(grep -c 'WAKE_SLICE\|WakeSlice' "$P")" = 0 ] || undo "the patch still names the wake slice"
echo "the patch: $(m8 "$O") -> $(m8 "$P"), exp 0372 lines 5, pad_audio_route header in, file list unchanged"
# 4
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || undo "the backend archive changed"
[ "$(m8 "$NB")" != "$NORMAL_OLD" ] && [ "$(m8 "$LB")" != "$LEAN_OLD" ] || undo "a binary did not change"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    plus=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' '); minus=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')
    echo "$v words: +[$plus] -[$minus]"
    [ "$plus" = "KYTY_BC5_0429_RR " ] || undo "$v gained other words than KYTY_BC5_0429_RR: $plus"
    [ "$minus" = "KYTY_BC5_0425_WAKE_SLICE_US " ] || undo "$v lost other words than KYTY_BC5_0425_WAKE_SLICE_US: $minus"
    s25=$(nice -n 19 strings "$b" | grep -c 'exp 0425'); s29=$(nice -n 19 strings "$b" | grep -c 'exp 0429')
    echo "$v: strings with 'exp 0425' $s25, with 'exp 0429' $s29"
    [ "$s25" = 0 ] || undo "$v still holds exp 0425 text"
    if [ $v = lean ]; then [ "$s29" = 0 ] || undo "lean holds exp 0429 text (a diagnostic)"; else [ "$s29" -ge 1 ] || undo "normal has no exp 0429 text"; fi
done
echo "int0429r done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$ARCH"); undo: bash $HERE/undo0429r.sh (to $PIN_OLD / $NORMAL_OLD / $LEAN_OLD / $ARCH_OLD)"
