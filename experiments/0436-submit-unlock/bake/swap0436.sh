#!/usr/bin/env bash
# BC5 exp 0436, the shared swap of the submit unlock BUILT IN, with no switch: no BC5_DIRECT_SUBMIT_UNLOCK (the
# maintainer, 2026-11-20: "Wdróż od razu"; his standing "usuń przełączniki i wybuduj w kod"). The form of exp 0433's
# int0433.sh (a backend step: direct.cpp and direct.hpp over the shared backend source, the archive rebuilt) with
# exp 0434's dry run.
#   1. checks: no emulator; the kit (md5s below); the shared tree's diff is 8986853b; normal 99f2a567, lean 82720cca,
#      archive 51db2c91; the shared backend source's direct.cpp 52f74d0e and direct.hpp 24988c4e (main's); both KytyPlus
#      builds include that backend source; the patch applies (git apply --check)
#   2. the lock (chain_claim, one line); copies under $X (*.before-0436: both binaries, the archive, direct.cpp,
#      direct.hpp, the unit the change edits, the old patch), read back; pins file
#   3. 0002-bc5-0436-baked.patch applied to the tree (git apply); the new patch = git diff f266548 must be PATCH_NEW;
#      exp 0372 = 5, the pad_audio_route header in, the same file list, the guard / learned / JOB_ARENA line counts as
#      before, no SUBMIT_UNLOCK text, su436's count line in
#   4. the backend: be/direct.cpp and be/direct.hpp over the shared source, read back
#      DRY=1 (the dry run on COPIES: INT_K=<copy of ~/src/KytyPlus>, INT_BES=<copy of the backend source>, X=<scratch>):
#      stops here, prints the new patch's md5, undoes the copies
#   5. the archive rebuilt (ninja bc5_backend, nice 19); it must change and carry Device::submit_impl
#   6. normal and lean rebuilt in place (ninja kyty_emulator, nice 19; they relink with the new archive)
#   7. strings: neither binary gains or loses a (KYTY_)BC5_ word; no SUBMIT_UNLOCK text in either; normal holds su436's
#      count line ("tag su436"), lean does not (compiled out)
# Any failure after step 2 runs undo0436.sh (everything back, checked by md5).
# usage (on the box, in the kit directory): PATCH_NEW=<md5 from the dry run> bash swap0436.sh
#                                           DRY=1 INT_K=<copy> INT_BES=<copy> X=<scratch> bash swap0436.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0436/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
BES0=$W/d19/export/backend; BES=${INT_BES:-$BES0}; CPP=$BES/src/direct.cpp; HPP=$BES/include/bc5/direct.hpp
PIN_OLD=8986853b; NORMAL_OLD=99f2a567; LEAN_OLD=82720cca; ARCH_OLD=51db2c91; CPP_OLD=52f74d0e; HPP_OLD=24988c4e
KIT_PATCH=3134afd1; KIT_CPP=eacf8d2a; KIT_HPP=9256f3b9; DRY=${DRY:-0}
PATCH_NEW=${PATCH_NEW:-}
UNITS="src/libs/bc5LleAgc.cpp"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "swap0436 STOP: $*"; exit 1; }
undo() { echo "swap0436: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_BES=$BES UNDO_DRY=$DRY bash "$HERE/undo0436.sh"; exit 1; }
words() { nice -n 19 strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in 0002-bc5-0436-baked.patch be/direct.cpp be/direct.hpp undo0436.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$HERE/0002-bc5-0436-baked.patch")" = "$KIT_PATCH" ] || stop "kit: the patch is $(m8 "$HERE/0002-bc5-0436-baked.patch"), not $KIT_PATCH"
[ "$(m8 "$HERE/be/direct.cpp")" = "$KIT_CPP" ] && [ "$(m8 "$HERE/be/direct.hpp")" = "$KIT_HPP" ] || stop "kit: be/direct.cpp or be/direct.hpp is not the pinned one"
[ "$DRY" = 1 ] || [ -n "$PATCH_NEW" ] || stop "PATCH_NEW is not given (take it from the dry run)"
if [ "$DRY" = 1 ]; then
    [ "$K" = "$HOME/src/KytyPlus" ] && stop "DRY=1 runs on a copy of the tree only (INT_K)"
    [ "$BES" = "$BES0" ] && stop "DRY=1 runs on a copy of the backend source only (INT_BES)"
    [ "$X" = "$W/exp0436/swap" ] && stop "DRY=1 keeps its copies apart (X)"
fi
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$CPP")" = "$CPP_OLD" ] && [ "$(m8 "$HPP")" = "$HPP_OLD" ] || stop "the backend source is direct.cpp $(m8 "$CPP") / direct.hpp $(m8 "$HPP"), not $CPP_OLD / $HPP_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
for b in kytyplus-build kytyplus-build-lean; do
    distrobox enter ubuntu -- sh -c "cd '$W/$b' && ninja -t compdb -x" < /dev/null 2> /dev/null | grep -q "$BES0/include" || stop "the KytyPlus build $b does not include $BES0/include"
done
(cd "$K" && git apply --check "$HERE/0002-bc5-0436-baked.patch") || stop "the patch does not apply to the tree"
# 2
if [ "$DRY" != 1 ]; then
    . "$N/chainlock0417.inc"
    chain_claim "exp 0436: shared swap, the submit unlock built in (no switch), patch $PIN_OLD -> $PATCH_NEW; archive, normal and lean rebuilt (CPU only, no emulator)" 60 || stop "no lock"
    trap chain_release EXIT
fi
[ -e "$X/pins.before-0436" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
if [ "$DRY" != 1 ]; then
    cp -p "$NB" "$X/kyty_emulator.normal.before-0436" && cp -p "$LB" "$X/kyty_emulator.lean.before-0436" \
      && cp -p "$ARCH" "$X/libbc5_backend.a.before-0436" || stop "cannot copy the binaries"
fi
cp -p "$CPP" "$X/direct.cpp.before-0436" && cp -p "$HPP" "$X/direct.hpp.before-0436" || stop "cannot copy the backend source"
for u in $UNITS; do mkdir -p "$X/units/$(dirname "$u")" && cp -p "$K/$u" "$X/units/$u" || stop "cannot copy $u"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0436.patch" || stop "cannot save the patch"
# shellcheck disable=SC2086
(cd "$K" && md5sum $UNITS) > "$X/units.md5" || stop "cannot sum the units"
{ echo "PIN_OLD=$PIN_OLD"; echo "CPP=$(m8 "$CPP")"; echo "HPP=$(m8 "$HPP")"
  if [ "$DRY" != 1 ]; then echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; fi; } > "$X/pins.before-0436"
[ "$(m8 "$X/0001.before-0436.patch")" = "$PIN_OLD" ] && (cd "$X/units" && md5sum -c --quiet "$X/units.md5") \
  && [ "$(m8 "$X/direct.cpp.before-0436")" = "$CPP_OLD" ] && [ "$(m8 "$X/direct.hpp.before-0436")" = "$HPP_OLD" ] || stop "the copies do not read back"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0436")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0436")" = "$LEAN_OLD" ] \
      && [ "$(m8 "$X/libbc5_backend.a.before-0436")" = "$ARCH_OLD" ] || stop "the binary copies do not read back"
    for v in normal lean; do words "$X/kyty_emulator.$v.before-0436" > "$X/words-$v.before"; done
fi
echo "before: $(tr '\n' ' ' < "$X/pins.before-0436")"
# 3
(cd "$K" && git apply "$HERE/0002-bc5-0436-baked.patch") || undo "git apply failed"
P=$X/0001-new0436.patch; O=$X/0001.before-0436.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ "$(files "$O")" = "$(files "$P")" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
grep -q 'SUBMIT_UNLOCK' "$P" && undo "a SUBMIT_UNLOCK word is in the patch"
grep -q 'tag su436' "$P" || undo "su436 is not in the patch"
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l), exp 0372 lines 5, pad_audio_route header in"
# 4
cp "$HERE/be/direct.cpp" "$CPP" && cp "$HERE/be/direct.hpp" "$HPP" || undo "cannot write the backend source"
[ "$(m8 "$CPP")" = "$KIT_CPP" ] && [ "$(m8 "$HPP")" = "$KIT_HPP" ] || undo "the backend source reads back as $(m8 "$CPP") / $(m8 "$HPP")"
echo "backend source: direct.cpp $CPP_OLD -> $KIT_CPP, direct.hpp $HPP_OLD -> $KIT_HPP"
if [ "$DRY" = 1 ]; then
    echo "swap0436 DRY: PATCH_NEW=$(m8 "$P"); undoing the copies"
    UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_BES=$BES UNDO_DRY=1 bash "$HERE/undo0436.sh"; exit $?
fi
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
# 5
echo "== $(date +%T) build the backend archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 ninja bc5_backend" < /dev/null > "$X/build-backend.log" 2>&1 || { grep -m12 "error" "$X/build-backend.log"; undo "the backend build failed"; }
[ "$(m8 "$ARCH")" != "$ARCH_OLD" ] || undo "the archive did not change"
nice -n 19 strings "$ARCH" | grep -q 'submit_impl' || undo "the archive lacks Device::submit_impl"
echo "archive: $ARCH_OLD -> $(m8 "$ARCH"), warnings $(grep -c 'warning:' "$X/build-backend.log"); steps $(grep -c '^\[' "$X/build-backend.log")"
# 6
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
# 7
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0436")" ] || undo "$v did not change"
    words "$b" > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ -z "$gained" ] && [ -z "$lost" ] || undo "$v: the words changed"
    nice -n 19 strings "$b" | grep -q 'SUBMIT_UNLOCK' && undo "$v: a SUBMIT_UNLOCK text is in the binary"
done
nice -n 19 strings "$NB" | grep -qF "tag su436" || undo "normal: su436's count line is not in the binary"
nice -n 19 strings "$LB" | grep -qF "tag su436" && undo "lean: su436's count line is in the binary"
echo "swap0436 done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0436.sh (to $PIN_OLD; further back: exp 0434's undo0434.sh)"
