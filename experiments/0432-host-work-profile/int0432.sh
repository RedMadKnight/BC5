#!/usr/bin/env bash
# BC5 exp 0432, the shared swap (exp 0430's int0430.sh adapted): the swap form of the host-work removal (Results 7-9):
# items D, W, M, R on, S and P in the backend, A, V and X compiled in and off (lean: off without a word), on top of the
# shared patch bc39a035. The top session's GO of 2026-11-18 after the scene A/B (34.4 against 32.2 flips/s, 6 of 6 clean).
#   1. checks: no emulator; the shared tree's diff is bc39a035; binaries 0de9349b / 63fda02d; archive 1423af83; the four
#      host units and the backend's direct.cpp pinned; the kit here
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0432/swap (*.before-0432), read back; pins file
#   3. swap432.diff applied to ~/src/KytyPlus (git apply); the four units must read as made on the laptop; the new patch
#      = git diff f266548 must be 940e8f36 (the 0001 patch on the branch); checks on it (exp 0372 = 5, the
#      pad_audio_route header, the same file list, BC5_GUARD_MAP_RULE / BC5_GUARD_PRT_BG / learned line counts as before)
#   4. the backend: be/direct.cpp in, the shared archive rebuilt in backend-ubuntu; normal and lean rebuilt in place
#      (ninja kyty_emulator, nice 19)
#   5. strings: no word lost; normal holds the nine new words and "tag d432"; lean holds none of the host unit's seven
# Any failure after step 2 runs undo0432.sh (units, backend source, archive and both binaries back, checked by md5).
# usage (on the box, in ~/bc5-work/exp0432/kit): bash int0432.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd); X=$W/exp0432/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
BES=$W/d19/export/backend; U5=$BES/src/direct.cpp; U5_OLD=5016c2a4; U5_NEW=52f74d0e; ARCH_OLD=1423af83
UN=(src/libs/bc5LleAgc.cpp src/common/platform/sysLinuxVirtual.cpp src/libs/libAmpr.cpp src/bc5/anon_sync.hpp)
UO=(b8afba59 2dcd6db3 5b2016ed 058bb712); UW=(f574f460 1262d6f3 a9a2143a 478ff14c)
PIN_OLD=bc39a035; PIN_NEW=940e8f36; NORMAL_OLD=0de9349b; LEAN_OLD=63fda02d
HOSTW="BC5_DIRECT_UNMAP_NOWAIT BC5_DIRECT_MAPS_FAST BC5_DIRECT_ANON_THREAD BC5_DIRECT_REFUSED_ENDS BC5_DIRECT_ANON_EVENTS BC5_DIRECT_VIEWS_KEPT BC5_DIRECT_MAPS_DIFF"
BEW="BC5_DIRECT_SLOT_GROW BC5_DIRECT_SLOT_PREALLOC"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0432 STOP: $*"; exit 1; }
undo() { echo "int0432: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0432.sh"; exit 1; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in swap432.diff undo0432.sh be/direct.cpp 0001-new0432.patch; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$HERE/be/direct.cpp")" = "$U5_NEW" ] || stop "be/direct.cpp is $(m8 "$HERE/be/direct.cpp"), not $U5_NEW"
[ "$(m8 "$HERE/0001-new0432.patch")" = "$PIN_NEW" ] || stop "the kit's patch is $(m8 "$HERE/0001-new0432.patch"), not $PIN_NEW"
[ "$(m8 "$U5")" = "$U5_OLD" ] || stop "the shared backend source is $(m8 "$U5"), not $U5_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the shared archive is $(m8 "$ARCH"), not $ARCH_OLD"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
for i in 0 1 2 3; do [ "$(m8 "$K/${UN[$i]}")" = "${UO[$i]}" ] || stop "${UN[$i]} is $(m8 "$K/${UN[$i]}"), not ${UO[$i]}"; done
git -C "$K" apply --check --whitespace=nowarn "$HERE/swap432.diff" || stop "swap432.diff does not apply to the shared tree"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0432: shared swap, the host-work removal (swap form; the backend archive rebuilt), patch $PIN_OLD + 0432; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
trap chain_release EXIT
[ -e "$X/kyty_emulator.normal.before-0432" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0432" && cp -p "$LB" "$X/kyty_emulator.lean.before-0432" \
  && cp -p "$U5" "$X/direct.cpp.before-0432" && cp -p "$ARCH" "$X/libbc5_backend.a.before-0432" || stop "cannot copy"
for i in 0 1 2 3; do cp -p "$K/${UN[$i]}" "$X/$(basename "${UN[$i]}").before-0432" || stop "cannot copy ${UN[$i]}"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0432.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; echo "U5=$(m8 "$U5")"
  for i in 0 1 2 3; do echo "U$((i + 1))=$(m8 "$K/${UN[$i]}")"; done; } > "$X/pins.before-0432"
[ "$(m8 "$X/kyty_emulator.normal.before-0432")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0432")" = "$LEAN_OLD" ] \
  && [ "$(m8 "$X/0001.before-0432.patch")" = "$PIN_OLD" ] && [ "$(m8 "$X/libbc5_backend.a.before-0432")" = "$ARCH_OLD" ] \
  && [ "$(m8 "$X/direct.cpp.before-0432")" = "$U5_OLD" ] || stop "the copies do not read back"
for i in 0 1 2 3; do [ "$(m8 "$X/$(basename "${UN[$i]}").before-0432")" = "${UO[$i]}" ] || stop "the copy of ${UN[$i]} does not read back"; done
echo "before: $(tr '\n' ' ' < "$X/pins.before-0432")"
for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0432" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.before"; done
# 3
git -C "$K" apply --whitespace=nowarn "$HERE/swap432.diff" || undo "swap432.diff did not apply"
for i in 0 1 2 3; do [ "$(m8 "$K/${UN[$i]}")" = "${UW[$i]}" ] || undo "the edited ${UN[$i]} is $(m8 "$K/${UN[$i]}"), not ${UW[$i]}"; done
git -C "$K" diff --no-color f266548 > "$X/0001-new0432.patch" || undo "cannot write the new patch"
P=$X/0001-new0432.patch; O=$X/0001.before-0432.patch
[ "$(m8 "$P")" = "$PIN_NEW" ] || undo "the new patch is $(m8 "$P"), not $PIN_NEW as on the branch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1"; }
[ "$(files "$O" | md5sum)" = "$(files "$P" | md5sum)" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
ch=$(diff "$O" "$P" | grep -c '^[<>]'); echo "the patch: $(m8 "$O") -> $(m8 "$P"), $ch lines differ, exp 0372 lines 5, pad_audio_route header in"
# 4a: the backend
cp "$HERE/be/direct.cpp" "$U5" || undo "cannot write the backend source"
echo "== $(date +%T) build the backend archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 ninja bc5_backend" < /dev/null > "$X/build-backend.log" 2>&1 || { grep -m12 "error" "$X/build-backend.log"; undo "the backend build failed"; }
[ "$(m8 "$ARCH")" != "$ARCH_OLD" ] || undo "the archive did not change"
for w in $BEW; do nice -n 19 strings "$ARCH" | grep -qF "$w" || undo "the archive lacks $w"; done
echo "archive: $ARCH_OLD -> $(m8 "$ARCH")"
# 4b
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"), steps $(grep -c '^\[' "$X/build-$v.log")"
done
[ "$(m8 "$NB")" != "$NORMAL_OLD" ] && [ "$(m8 "$LB")" != "$LEAN_OLD" ] || undo "a binary did not change"
# 5
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    nice -n 19 strings "$b" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u > "$X/words-$v.after"
    echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ')]; 'tag d432': $(nice -n 19 strings "$b" | grep -c 'tag d432')"
    [ -z "$(comm -23 "$X/words-$v.before" "$X/words-$v.after")" ] || undo "$v: words were lost"
    for w in $BEW; do grep -qx "$w" "$X/words-$v.after" || undo "$v lacks $w"; done
done
for w in $HOSTW; do
    grep -qx "$w" "$X/words-normal.after" || undo "normal lacks $w"
    grep -qx "$w" "$X/words-lean.after" && undo "lean holds $w"
done
[ "$(nice -n 19 strings "$NB" | grep -c 'tag d432')" -ge 1 ] || undo "normal lacks the d432 line"
[ "$(nice -n 19 strings "$LB" | grep -c 'tag d432')" = 0 ] || undo "lean holds the d432 line"
echo "int0432 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"), archive $(m8 "$ARCH"); undo: bash $W/exp0432/undo0432.sh"
