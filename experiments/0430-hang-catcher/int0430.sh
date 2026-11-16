#!/usr/bin/env bash
# BC5 exp 0430, the swap of the hang fix (exp 0428's int0428b.sh adapted): F3 and F2 (tag ho430, the shared form of
# mkswap0430.py: BC5_DIRECT_XQ_ACQUIRE and BC5_DIRECT_XQ_PENDING, each on unless "0"; they act only when rings run side
# by side), on top of the shared patch a8717e53. Only src/libs/bc5LleAgc.cpp changes. The maintainer's consent for way 2
# "until full deployment" and the top session's night plan of 2026-11-16.
#   1. checks: no emulator; the shared tree's diff is a8717e53; both binaries are dae7bf0b / 819f3b05; units pinned; kit here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0430/swap (*.before-0430), read back; pins file
#   3. mkswap0430.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 = 5, the pad_audio_route
#      header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned / JOB_ARENA line counts as before)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds gain exactly BC5_DIRECT_XQ_ACQUIRE and BC5_DIRECT_XQ_PENDING and lose none
# Any failure after step 2 runs undo0430.sh (both units and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0430): bash int0430.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0430/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
U1=$K/src/libs/bc5LleAgc.cpp; U2=$K/src/bc5/switch_defaults.hpp
PIN_OLD=a8717e53; NORMAL_OLD=dae7bf0b; LEAN_OLD=819f3b05; U1_OLD=0cda79b5; U2_OLD=${U2_PIN:?U2_PIN: the shared switch_defaults.hpp md5, read before}; U1_NEW=42f9f976; U2_NEW=$U2_OLD
NEW="BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_PENDING"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0430 STOP: $*"; exit 1; }
undo() { echo "int0430: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0430.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkswap0430.py ho430.cpp undo0430.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$U1")" = "$U1_OLD" ] && [ "$(m8 "$U2")" = "$U2_OLD" ] || stop "the units are $(m8 "$U1") / $(m8 "$U2"), not $U1_OLD / $U2_OLD"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0430: shared swap, the hang fix (ho430: F3 + F2), patch $PIN_OLD + 0430; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0430" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0430" && cp -p "$LB" "$X/kyty_emulator.lean.before-0430" \
  && cp -p "$U1" "$X/bc5LleAgc.cpp.before-0430" && cp -p "$U2" "$X/switch_defaults.hpp.before-0430" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0430.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "U2=$(m8 "$U2")"; echo "ARCH=$(m8 "$ARCH")"; } > "$X/pins.before-0430"
[ "$(m8 "$X/kyty_emulator.normal.before-0430")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0430")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/0001.before-0430.patch")" = "$PIN_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0430")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0430" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkswap0430.py" "$K" || undo "mkswap0430.py refused"
[ "$(m8 "$U1")" = "$U1_NEW" ] && [ "$(m8 "$U2")" = "$U2_NEW" ] || undo "the edited units are $(m8 "$U1") / $(m8 "$U2"), not $U1_NEW / $U2_NEW"
git -C "$K" diff --no-color f266548 > "$X/0001-new0430.patch" || undo "cannot write the new patch"
P=$X/0001-new0430.patch; O=$X/0001.before-0430.patch
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
[ "$(m8 "$ARCH")" = "$(grep '^ARCH=' "$X/pins.before-0430" | cut -d= -f2)" ] || undo "the backend archive changed"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'ho430 F3': $(nice -n 19 strings "$b" | grep -c 'ho430 F3')"
done
for v in normal lean; do
    [ "$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')" = "$NEW" ] || undo "$v: the words gained are not exactly [$NEW]"
    [ -z "$(comm -23 "$X/words-$v.before" "$X/words-$v.after")" ] || undo "$v: words were lost: $(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')"
done
echo "int0430 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0430.sh (then exp 0428's undo0428b.sh); rollback without a build: BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_PENDING=0"
