#!/usr/bin/env bash
# BC5 exp 0430, the swap of F5, the precise form (int0430.sh adapted by mkintf5.py, 2026-11-17): BC5_DIRECT_XQ_PRECISE
# (on unless "0") on top of the shared tree as it is when it runs (the hang fix F3 + F4 swapped at 07:10, then exps 0431
# and 0429). Only src/libs/bc5LleAgc.cpp changes (b8afba59 -> 574301e4, mkf5.py); the backend is not touched. The top
# session's gate of 2026-11-17 10:50 (P: no GPU hang or fault in any run, mean >= S's mean - 1 flips/s).
#   1. checks: no emulator; the shared tree's diff, normal and lean are the pins given (read just before); units pinned
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0430/swapf5 (*.before-0430), read back; pins file
#   3. mkf5.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 lines and every guarded count
#      as before, the pad_audio_route header, the same file list)
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same
#   5. strings: both builds gain exactly BC5_DIRECT_XQ_PRECISE and lose none
# Any failure after step 2 runs undo0430.sh with X=swapf5 (units, binaries, backend files and archive back, by md5).
# usage (on the box, in ~/bc5-work/exp0430): PIN_PIN=<tree diff md5> NORMAL_PIN=<md5> LEAN_PIN=<md5> U2_PIN=<md5> bash int0430f5.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0430/swapf5
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
# the backend: only copied and checked, never rebuilt (F4's archive since 07:10)
BES=$W/d19/export/backend; U3=$BES/src/direct.cpp; U4=$BES/include/bc5/direct.hpp; U3_OLD=5016c2a4; U4_OLD=24988c4e; ARCH_OLD=1423af83
U1=$K/src/libs/bc5LleAgc.cpp; U2=$K/src/bc5/switch_defaults.hpp
PIN_OLD=${PIN_PIN:?PIN_PIN: the shared tree diff md5, read before}; NORMAL_OLD=${NORMAL_PIN:?NORMAL_PIN}; LEAN_OLD=${LEAN_PIN:?LEAN_PIN}; U1_OLD=b8afba59; U2_OLD=${U2_PIN:?U2_PIN: the shared switch_defaults.hpp md5, read before}; U1_NEW=574301e4; U2_NEW=$U2_OLD
NEW="BC5_DIRECT_XQ_PRECISE"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0430f5 STOP: $*"; exit 1; }
undo() { echo "int0430f5: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X bash "$HERE/undo0430.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in mkf5.py ho430.cpp ho430.b8.cpp undo0430.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$U3")" = "$U3_OLD" ] && [ "$(m8 "$U4")" = "$U4_OLD" ] || stop "the shared backend source is $(m8 "$U3") / $(m8 "$U4"), not $U3_OLD / $U4_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the shared archive is $(m8 "$ARCH"), not $ARCH_OLD"
for b in kytyplus-build kytyplus-build-lean; do distrobox enter ubuntu -- sh -c "cd '$W/$b' && ninja -t compdb -x" < /dev/null 2> /dev/null | grep -q "$BES/include" || stop "the KytyPlus build $b does not include $BES/include"; done
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$U1")" = "$U1_OLD" ] && [ "$(m8 "$U2")" = "$U2_OLD" ] || stop "the units are $(m8 "$U1") / $(m8 "$U2"), not $U1_OLD / $U2_OLD"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0430: shared swap of F5 (the precise form, BC5_DIRECT_XQ_PRECISE), patch $PIN_OLD + F5; normal and lean rebuilt (CPU only, no emulator)" 30 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0430" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0430" && cp -p "$LB" "$X/kyty_emulator.lean.before-0430" \
  && cp -p "$U1" "$X/bc5LleAgc.cpp.before-0430" && cp -p "$U2" "$X/switch_defaults.hpp.before-0430" \
  && cp -p "$U3" "$X/direct.cpp.before-0430" && cp -p "$U4" "$X/direct.hpp.before-0430" && cp -p "$ARCH" "$X/libbc5_backend.a.before-0430" || stop "cannot copy"
git -C "$K" diff --no-color f266548 > "$X/0001.before-0430.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "U1=$(m8 "$U1")"; echo "U2=$(m8 "$U2")"; echo "ARCH=$(m8 "$ARCH")"; echo "U3=$(m8 "$U3")"; echo "U4=$(m8 "$U4")"; } > "$X/pins.before-0430"
[ "$(m8 "$X/kyty_emulator.normal.before-0430")" = "$(m8 "$NB")" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0430")" = "$(m8 "$LB")" ] \
  && [ "$(m8 "$X/0001.before-0430.patch")" = "$PIN_OLD" ] && [ "$(m8 "$X/libbc5_backend.a.before-0430")" = "$ARCH_OLD" ] || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0430")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0430" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
python3 -I "$HERE/mkf5.py" "$K" || undo "mkf5.py refused"
[ "$(m8 "$U1")" = "$U1_NEW" ] && [ "$(m8 "$U2")" = "$U2_NEW" ] || undo "the edited units are $(m8 "$U1") / $(m8 "$U2"), not $U1_NEW / $U2_NEW"
git -C "$K" diff --no-color f266548 > "$X/0001-new0430.patch" || undo "cannot write the new patch"
P=$X/0001-new0430.patch; O=$X/0001.before-0430.patch
[ "$(grep -c 'exp 0372' "$P")" = "$(grep -c 'exp 0372' "$O")" ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$O") -> $(grep -c 'exp 0372' "$P")"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines $(grep -c 'exp 0372' "$P"), pad_audio_route header in"
# 4b
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
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'ho430 F5': $(nice -n 19 strings "$b" | grep -c 'ho430 F5')"
done
for v in normal lean; do
    [ "$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')" = "$NEW" ] || undo "$v: the words gained are not exactly [$NEW]"
    [ -z "$(comm -23 "$X/words-$v.before" "$X/words-$v.after")" ] || undo "$v: words were lost: $(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')"
done
echo "int0430f5 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: X=$X bash $HERE/undo0430.sh; rollback without a build: BC5_DIRECT_XQ_PRECISE=0"
