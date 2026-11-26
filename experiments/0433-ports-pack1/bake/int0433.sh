#!/usr/bin/env bash
# BC5 exp 0433, the shared swap of ports pack 1 BUILT IN: all 14 fixes on, no KYTY_BC5_P1_* switch (the top session's ask
# of 2026-11-19, the 0430 bake's form; the pack measured cost-neutral within noise, README "Results on the box"). Run by
# the top session, only on the maintainer's word. CONTEXT_REG_RMW (0x51) stays counted only: no pass row, no packet change.
#   1. checks: no emulator; the kit (md5s below); the shared tree's diff is d1388db0 and has no ports_pack1.hpp; normal
#      eb85d32e, lean 364c6146, archive 6eac453e; the shared backend source's policy.cpp d5ae7298 (main ba402356); both
#      KytyPlus builds include that backend source
#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0433/swap (*.before-0433: both binaries, the archive,
#      policy.cpp, the 17 units the pack changes, the old patch), read back; pins file
#   3. 0002-bc5-ports-pack1-baked.patch applied to ~/src/KytyPlus (git apply), its one new file marked with git add -N
#      (so `git diff f266548` shows it, as the other headers of patch 0001); the new patch = git diff f266548 must be
#      PATCH_NEW; exp 0372 = 5, the pad_audio_route header in, the old file list kept plus three files, the guard /
#      learned / JOB_ARENA line counts as before
#   4. the backend: be/policy.cpp (main's policy.cpp + policy0433.diff, the 0x51 count) over the shared source; the
#      archive rebuilt (ninja bc5_backend); it must change and carry the count's line
#   5. normal and lean rebuilt in place (ninja kyty_emulator, nice 19; they relink with the new archive)
#   6. strings: neither binary gains or loses a (KYTY_)BC5_ word; no KYTY_BC5_P1_ text in either; both carry the 0x51
#      count's line; normal carries the hit counts' line, lean does not
# Any failure after step 2 runs undo0433.sh (everything back, checked by md5).
# usage (on the box, in the kit directory): bash int0433.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0433/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
BES=$W/d19/export/backend; POL=$BES/src/policy.cpp
PIN_OLD=d1388db0; NORMAL_OLD=${NORMAL_OLD:-eb85d32e}; LEAN_OLD=${LEAN_OLD:-364c6146}; ARCH_OLD=${ARCH_OLD:-6eac453e}; POL_OLD=d5ae7298
KIT_PATCH=e3124f5d; KIT_POL=107bb1b6; PATCH_NEW=59f00d27
NEWF=src/bc5/ports_pack1.hpp
UNITS="src/common/hostException.cpp src/common/hostException.h src/common/platform/sysLinuxFileIO.cpp src/common/platform/sysLinuxVirtual.cpp src/common/threads.cpp src/kernel/eventQueue.cpp src/kernel/memory.cpp src/kernel/pthread.cpp src/kernel/semaphore.cpp src/libs/ajm.cpp src/libs/controller.cpp src/libs/libAmpr.cpp src/libs/libAppContent.cpp src/libs/libSaveData.cpp src/libs/libSysmodule.cpp src/libs/libUserService.cpp src/libs/network.cpp"
RMW="CONTEXT_REG_RMW (0x51)"; HITS="ports pack 1 hits"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0433 STOP: $*"; exit 1; }
undo() { echo "int0433: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K bash "$HERE/undo0433.sh"; exit 1; }
words() { nice -n 19 strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in 0002-bc5-ports-pack1-baked.patch be/policy.cpp undo0433.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$HERE/0002-bc5-ports-pack1-baked.patch")" = "$KIT_PATCH" ] || stop "kit: the patch is $(m8 "$HERE/0002-bc5-ports-pack1-baked.patch"), not $KIT_PATCH"
[ "$(m8 "$HERE/be/policy.cpp")" = "$KIT_POL" ] || stop "kit: be/policy.cpp is $(m8 "$HERE/be/policy.cpp"), not $KIT_POL"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the shared tree's diff is $(tdiff), not $PIN_OLD"
[ -e "$K/$NEWF" ] && stop "$K/$NEWF exists already"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
[ "$(m8 "$POL")" = "$POL_OLD" ] || stop "the shared backend's policy.cpp is $(m8 "$POL"), not $POL_OLD"
for b in kytyplus-build kytyplus-build-lean; do
    distrobox enter ubuntu -- sh -c "cd '$W/$b' && ninja -t compdb -x" < /dev/null 2> /dev/null | grep -q "$BES/include" || stop "the KytyPlus build $b does not include $BES/include"
done
(cd "$K" && git apply --check "$HERE/0002-bc5-ports-pack1-baked.patch") || stop "the patch does not apply to the shared tree"
# 2
. "$N/chainlock0417.inc"
chain_claim "exp 0433: shared swap, ports pack 1 built in (14 fixes, no switch; 0x51 counted only), patch $PIN_OLD -> $PATCH_NEW; archive, normal and lean rebuilt (CPU only, no emulator)" 60 || stop "no lock"
trap chain_release EXIT
[ -e "$X/pins.before-0433" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
cp -p "$NB" "$X/kyty_emulator.normal.before-0433" && cp -p "$LB" "$X/kyty_emulator.lean.before-0433" \
  && cp -p "$ARCH" "$X/libbc5_backend.a.before-0433" && cp -p "$POL" "$X/policy.cpp.before-0433" || stop "cannot copy"
for u in $UNITS; do mkdir -p "$X/units/$(dirname "$u")" && cp -p "$K/$u" "$X/units/$u" || stop "cannot copy $u"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0433.patch" || stop "cannot save the patch"
(cd "$K" && md5sum $UNITS) > "$X/units.md5" || stop "cannot sum the units"
{ echo "PIN_OLD=$PIN_OLD"; echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; echo "POL=$(m8 "$POL")"; } > "$X/pins.before-0433"
[ "$(m8 "$X/kyty_emulator.normal.before-0433")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0433")" = "$LEAN_OLD" ] \
  && [ "$(m8 "$X/libbc5_backend.a.before-0433")" = "$ARCH_OLD" ] && [ "$(m8 "$X/policy.cpp.before-0433")" = "$POL_OLD" ] \
  && [ "$(m8 "$X/0001.before-0433.patch")" = "$PIN_OLD" ] && (cd "$X/units" && md5sum -c --quiet "$X/units.md5") || stop "the copies do not read back"
echo "before: $(tr '\n' ' ' < "$X/pins.before-0433")"
for v in normal lean; do words "$X/kyty_emulator.$v.before-0433" > "$X/words-$v.before"; done
# 3
(cd "$K" && git apply "$HERE/0002-bc5-ports-pack1-baked.patch") || undo "git apply failed"
git -C "$K" add -N "$NEWF" || undo "git add -N $NEWF failed"
P=$X/0001-new0433.patch; O=$X/0001.before-0433.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ -z "$(comm -23 <(files "$O") <(files "$P"))" ] || undo "a file left the patch: $(comm -23 <(files "$O") <(files "$P") | tr '\n' ' ')"
[ "$(comm -13 <(files "$O") <(files "$P") | wc -l)" = 3 ] || undo "files new to the patch: $(comm -13 <(files "$O") <(files "$P") | tr '\n' ' '), not 3"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l), exp 0372 lines 5, pad_audio_route header in"
# 4
cp "$HERE/be/policy.cpp" "$POL" || undo "cannot write policy.cpp"
[ "$(m8 "$POL")" = "$KIT_POL" ] || undo "policy.cpp reads back as $(m8 "$POL")"
echo "== $(date +%T) build the backend archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 ninja bc5_backend" < /dev/null > "$X/build-backend.log" 2>&1 || { grep -m12 "error" "$X/build-backend.log"; undo "the backend build failed"; }
[ "$(m8 "$ARCH")" != "$ARCH_OLD" ] || undo "the archive did not change"
nice -n 19 strings "$ARCH" | grep -qF "$RMW" || undo "the archive lacks the 0x51 count"
echo "archive: $ARCH_OLD -> $(m8 "$ARCH")"
# 5
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
# 6
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0433")" ] || undo "$v did not change"
    words "$b" > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ -z "$gained" ] && [ -z "$lost" ] || undo "$v: the words changed"
    nice -n 19 strings "$b" | grep -qF "KYTY_BC5_P1_" && undo "$v: a KYTY_BC5_P1_ text is in the binary"
    nice -n 19 strings "$b" | grep -qF "$RMW" || undo "$v: the 0x51 count is not in the binary"
done
nice -n 19 strings "$NB" | grep -qF "$HITS" || undo "normal: the hit counts are not in the binary"
nice -n 19 strings "$LB" | grep -qF "$HITS" && undo "lean: the hit counts are in the binary"
echo "int0433 done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0433.sh (to $PIN_OLD; further back: exp 0430's undo0430b.sh)"
