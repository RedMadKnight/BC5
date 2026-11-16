#!/usr/bin/env bash
# BC5 exp 0428, the SECOND swap (int0428.sh adapted): iteration 6's split fix (BC5_DIRECT_ACB_SPLIT_LATE=3, a fifth PPSA03671
# way-2 row; the unit as tested in build 185a18f8), on top of the shared patch 2c82a979 (the first swap). The
# maintainer's consent through deployment (relayed by the top session, 2026-11-16) and the top session's GO.
#   1. checks: no emulator; the shared tree's diff is 700fd4c2; both binaries are 1be1cc1d / b7fb337f; units pinned; kit here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0428/swap (*.before-0428b), read back; pins file
#   3. mkswap0428.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the pad_audio_route
#      header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned / JOB_ARENA line counts as before)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds gain exactly the four exp 0428 words and lose none; normal holds "tag w428c", lean no
#      "exp 0428" text
# Any failure after step 2 runs undo0428.sh (both units and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0428): bash int0428.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0428/swap2; BASE=$W/exp0428/swap/bc5LleAgc.cpp.before-0428
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
U1=$K/src/libs/bc5LleAgc.cpp; U2=$K/src/bc5/switch_defaults.hpp
PIN_OLD=2c82a979; NORMAL_OLD=3f22e0e1; LEAN_OLD=35a3753d; U1_OLD=f16eb3f3; U2_OLD=3b41711e; U1_NEW=0cda79b5; U2_NEW=554e0139
NEW="BC5_DIRECT_ACB_SPLIT_LATE"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0428b STOP: $*"; exit 1; }
undo() { echo "int0428b: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0428b.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkswap0428b.py mk0428.py ed0419g.py undo0428b.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$U1")" = "$U1_OLD" ] && [ "$(m8 "$U2")" = "$U2_OLD" ] || stop "the units are $(m8 "$U1") / $(m8 "$U2"), not $U1_OLD / $U2_OLD"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0428: second shared swap, the split fix (SPLIT_LATE=3) for the second title, patch $PIN_OLD + 0428b; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0428b" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0428b" && cp -p "$LB" "$X/kyty_emulator.lean.before-0428b" \
  && cp -p "$U1" "$X/bc5LleAgc.cpp.before-0428b" && cp -p "$U2" "$X/switch_defaults.hpp.before-0428b" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0428b.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "U2=$(m8 "$U2")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0428b"
[ "$(m8 "$X/kyty_emulator.normal.before-0428b")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0428b")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/0001.before-0428b.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0428b")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0428b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
[ "$(m8 "$BASE")" = 3e847e03 ] || undo "the base unit $BASE is not 3e847e03"
python3 -I "$HERE/mkswap0428b.py" "$K" "$BASE" || undo "mkswap0428b.py refused"
[ "$(m8 "$U1")" = "$U1_NEW" ] && [ "$(m8 "$U2")" = "$U2_NEW" ] || undo "the edited units are $(m8 "$U1") / $(m8 "$U2"), not $U1_NEW / $U2_NEW"
git -C "$K" diff --no-color f266548 > "$X/0001-new0428b.patch" || undo "cannot write the new patch"
P=$X/0001-new0428b.patch; O=$X/0001.before-0428b.patch
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
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
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), of them in bc5LleAgc.cpp: $(grep -c 'bc5LleAgc.cpp.*warning' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0428b" | cut -d= -f2)" ] || undo "the backend archive changed"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'tag w428c': $(nice -n 19 strings "$b" | grep -c 'tag w428c'), 'exp 0428': $(nice -n 19 strings "$b" | grep -c 'exp 0428')"
done
for v in normal lean; do
    [ "$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')" = "$NEW" ] || undo "$v: the words gained are not exactly [$NEW]"
    [ -z "$(comm -23 "$X/words-$v.before" "$X/words-$v.after")" ] || undo "$v: words were lost: $(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')"
done
[ "$(nice -n 19 strings "$LB" | grep -c 'exp 0428')" = 0 ] || undo "lean holds exp 0428 text"
[ "$(nice -n 19 strings "$NB" | grep -c 'tag w428c')" -ge 1 ] || undo "normal lacks the w428c line"
echo "int0428b done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0428b.sh (then undo0428.sh for way 2 itself); rollback without a build: BC5_DIRECT_ACB_SPLIT_LATE=0"
