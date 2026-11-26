#!/usr/bin/env bash
# BC5 exp 0431, the shared swap (exp 0428's int0428b.sh adapted): way 2 for EVERY title. The five way-2 rows move from
# TITLE2's kTitleDefaults to kSoft (mkswap0431.py); the unit bc5LleAgc.cpp (b8afba59 since exp 0430) is not touched. On top of the
# shared patch a7c1653d (exp 0430, rebased from a8717e53). The maintainer's word (way 2 must be in any game, 2026-11-16) and the top session's GO.
#   1. checks: no emulator; the shared tree's diff is a7c1653d; both binaries are bf3f5f00 / 0fb7bed5; units pinned; kit here
#   2. the lock (chain_claim, one line; or the chain's line in CHAIN_LOCKLINE); copies under ~/bc5-work/exp0431/swap
#      (*.before-0431), read back; pins file
#   3. mkswap0431.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the pad_audio_route
#      header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned / JOB_ARENA line counts as before; no
#      TITLE2 ACB row left, five kSoft ACB rows)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds gain and lose NO word (the five words were in both already); normal holds "tag w428c", lean
#      no "exp 0428" text
# Any failure after step 2 runs undo0431.sh (both units and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0431): bash int0431.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0431/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
U1=$K/src/libs/bc5LleAgc.cpp; U2=$K/src/bc5/switch_defaults.hpp
PIN_OLD=a7c1653d; NORMAL_OLD=bf3f5f00; LEAN_OLD=0fb7bed5; U1_OLD=b8afba59; U2_OLD=554e0139; U1_NEW=b8afba59; U2_NEW=40ac1ac2  # rebased 2026-11-17 on exp 0430's swap
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0431 STOP: $*"; exit 1; }
undo() { echo "int0431: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0431.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkswap0431.py ed0419g.py undo0431.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$U1")" = "$U1_OLD" ] && [ "$(m8 "$U2")" = "$U2_OLD" ] || stop "the units are $(m8 "$U1") / $(m8 "$U2"), not $U1_OLD / $U2_OLD"
# 2
. "$N/chainlock0417.inc"
if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$W/BOX-LOCK")" = "$CHAIN_LOCKLINE" ]; then
    echo "int0431: in the chain's slot"
else
    chain_claim "exp 0431: shared swap, way 2 for every title (five rows to kSoft), patch $PIN_OLD + 0431; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
    trap chain_release EXIT
fi
[ -e "$X/kyty_emulator.normal.before-0431" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0431" && cp -p "$LB" "$X/kyty_emulator.lean.before-0431" \
  && cp -p "$U1" "$X/bc5LleAgc.cpp.before-0431" && cp -p "$U2" "$X/switch_defaults.hpp.before-0431" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0431.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "U2=$(m8 "$U2")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0431"
[ "$(m8 "$X/kyty_emulator.normal.before-0431")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0431")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/0001.before-0431.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0431")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0431" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkswap0431.py" "$K" || undo "mkswap0431.py refused"
[ "$(m8 "$U1")" = "$U1_NEW" ] && [ "$(m8 "$U2")" = "$U2_NEW" ] || undo "the edited units are $(m8 "$U1") / $(m8 "$U2"), not $U1_NEW / $U2_NEW"
git -C "$K" diff --no-color f266548 > "$X/0001-new0431.patch" || undo "cannot write the new patch"
P=$X/0001-new0431.patch; O=$X/0001.before-0431.patch
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
[ "$(grep -c '{BC5_T2, "BC5_DIRECT_ACB' "$P")" = 0 ] || undo "a TITLE2 ACB row is left"
[ "$(grep -c '^+    {"BC5_DIRECT_ACB_\(RINGS\|QUEUE_STATE\|MEC_INDIRECT\|STATE_NO_WALK\|SPLIT_LATE\)", "[0-9]"},$' "$P")" = 5 ] || undo "not the five way-2 rows in kSoft"
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5, pad_audio_route header in"
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
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0431" | cut -d= -f2)" ] || undo "the backend archive changed"
[ "$(m8 "$NB")" != "$NORMAL_OLD" ] && [ "$(m8 "$LB")" != "$LEAN_OLD" ] || undo "a binary did not change"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'tag w428c': $(nice -n 19 strings "$b" | grep -c 'tag w428c'), 'exp 0428': $(nice -n 19 strings "$b" | grep -c 'exp 0428')"
    cmp -s "$X/words-$v.before" "$X/words-$v.after" || undo "$v: the words changed"
    for w in BC5_DIRECT_ACB_RINGS BC5_DIRECT_ACB_QUEUE_STATE BC5_DIRECT_ACB_MEC_INDIRECT BC5_DIRECT_ACB_STATE_NO_WALK BC5_DIRECT_ACB_SPLIT_LATE; do
        grep -qx "$w" "$X/words-$v.after" || undo "$v lacks $w"
    done
done
[ "$(nice -n 19 strings "$LB" | grep -c 'exp 0428')" = 0 ] || undo "lean holds exp 0428 text"
[ "$(nice -n 19 strings "$NB" | grep -c 'tag w428c')" -ge 1 ] || undo "normal lacks the w428c line"
echo "int0431 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0431.sh (then exp0430/undo0430.sh further back); rollback without a build: BC5_DIRECT_ACB_RINGS=0"
