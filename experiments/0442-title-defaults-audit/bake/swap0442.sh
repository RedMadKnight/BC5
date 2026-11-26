#!/usr/bin/env bash
# BC5 exp 0442 (tag bake442, "bake 1"): the shared swap of the every-title, nothing-learned build. swap0438b.sh's shape,
# with whole files in place of a patch (the kit's files are the ones box0442b.sh built and test0442.sh checked):
#   host (the KytyPlus tree, patch 589ef163): src/bc5/switch_defaults.hpp, src/libs/bc5LleAgc.cpp,
#        src/graphics/presentation/settingsOverlay.cpp, src/bc5/load_stat.hpp replaced (old and new md5 pinned in
#        pins0442.inc), src/bc5/idraws0442.hpp added and staged (git add, as the patch's other new files are), so the
#        patch's file list gains exactly that one file
#   backend (the shared source $B = ~/bc5-work/d19/export/backend, built in ~/bc5-work/backend-ubuntu): src/direct.cpp,
#        src/indirect_check.cpp, src/shadow_labels.cpp and their three headers replaced; CMakeLists.txt edited (the
#        library loses src/host_indirect.cpp, the test list loses the two deleted tests; the box's export keeps its own
#        older test and experiment lines, BC5_BUILD_TESTS is OFF in backend-ubuntu); deleted: host_indirect.{hpp,cpp},
#        zero_skip.hpp, tests/host_indirect_test.cpp, tests/zero_skip_test.cpp
#   1. checks: BOX-LOCK empty (or our caller's line), no emulator, no exp 0439 unit (b439*); the kit's files by md5; the
#      tree's diff 589ef163 and its four files the pinned ones, no idraws0442.hpp; the backend's 7 + 5 files the pinned
#      ones; both CMake caches point at $B and backend-ubuntu; normal 30546370, lean 05fd749d, archive a548a249;
#      box0442b.sh's private build present (its word lists are the swap's reference)
#   2. the lock (chain_claim, one line); copies under $X (*.before-0442: both binaries, the archive, every file touched)
#   3. the files in; the new patch = git diff f266548 must be PATCH_NEW; exp 0372 lines 5, the pad_audio_route header in,
#      the file list = the old one + src/bc5/idraws0442.hpp; JOB_ARENA, MAP_RULE, PRT_BG line counts unchanged; no
#      learned file name or learned seam in the patch; kGeneric0442 and kGone0442 in. DRY=1 (on COPIES: INT_K=<copy of
#      ~/src/KytyPlus>, INT_B=<copy of the backend source>, X=<scratch>): stops here, prints the new patch's md5, undoes
#   4. the archive rebuilt (ninja bc5_backend), then normal and lean (ninja kyty_emulator), nice 19
#   5. the archive changed; both binaries changed; their switch words gained and lost exactly what box0442b.sh's private
#      build gained and lost against the same shared binaries (priv5/<v>/strings*.txt, bake 1c); the 28 moved words in; no
#      "direct-aliases-pkg.txt", "direct-learned" or "learn:" text in the archive or either binary
# Any failure after step 2 runs undo0442.sh (everything back to 589ef163 / 30546370 / 05fd749d / a548a249, by md5).
# usage (on the box, in the kit directory): PATCH_NEW=<md5 from the dry run> bash swap0442.sh
#                                           DRY=1 INT_K=<copy> INT_B=<copy> X=<scratch> bash swap0442.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; B=${INT_B:-$W/d19/export/backend}; BB=$W/backend-ubuntu
HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0442/swap}; PRIV=$W/exp0442/priv5
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$BB/libbc5_backend.a
PIN_OLD=589ef163; NORMAL_OLD=30546370; LEAN_OLD=05fd749d; ARCH_OLD=a548a249
DRY=${DRY:-0}; PATCH_NEW=${PATCH_NEW:-}
HOST_FILES=; HOST_ADD=; BE_FILES=; BE_GONE=
. "$HERE/pins0442.inc" || { echo "swap0442 STOP: no pins0442.inc"; exit 1; }
MOVED="KYTY_BC5_SAVEDATA_MEMORY_FIXES KYTY_BC5_SAVEDATA_DELETE_BUSY KYTY_BC5_SAVEDATA_ALIASES KYTY_BC5_HTTP2_FIXES KYTY_BC5_PAD_OPEN_EXT
KYTY_BC5_JSON2_FIXES KYTY_BC5_ULT_FIXES KYTY_BC5_USERSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000
KYTY_BC5_AUDIOOUT_CHECKS KYTY_BC5_AUDIOIN_CHECKS KYTY_BC5_NGS2_RACK_FIX KYTY_BC5_FW_PAD KYTY_BC5_LOAD_ZLIB KYTY_BC5_LOAD_JPEG
KYTY_BC5_LOAD_IME KYTY_BC5_LOAD_NPCOMMON KYTY_BC5_LOAD_NPMANAGER KYTY_BC5_LOAD_NPTROPHY BC5_DIRECT_MEC_INDIRECT
BC5_DIRECT_REMEMBER_UNMAPPED KYTY_BC5_APR_PARALLEL BC5_DIRECT_GPU_CHECK BC5_DIRECT_DMA_SNAPSHOT BC5_DIRECT_CS_PREFIX
BC5_DIRECT_INDIRECT_DRAWS BC5_DIRECT_LAZY_RELEASE"
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "swap0442 STOP: $*"; exit 1; }
undo() { echo "swap0442: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_B=$B UNDO_DRY=$DRY bash "$HERE/undo0442.sh"; exit 1; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
line() { comm "$1" <(words "$2") <(words "$3") | tr '\n' ' ' | sed 's/ $//'; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
systemctl --user list-units --state=active --no-legend 'b439*' 2> /dev/null | grep -q . && stop "an exp 0439 unit (b439*) is active"
[ -n "$HOST_FILES" ] && [ -n "$HOST_ADD" ] && [ -n "$BE_FILES" ] && [ -n "$BE_GONE" ] || stop "kit: pins0442.inc is incomplete"
[ -s "$HERE/undo0442.sh" ] || stop "kit: undo0442.sh missing"
for e in $HOST_FILES; do IFS=: read -r p o n f <<< "$e"; [ "$(m8 "$HERE/host/$f")" = "$n" ] || stop "kit: host/$f is $(m8 "$HERE/host/$f"), not $n"; done
IFS=: read -r ADD_P ADD_N ADD_F <<< "$HOST_ADD"; [ "$(m8 "$HERE/host/$ADD_F")" = "$ADD_N" ] || stop "kit: host/$ADD_F is not $ADD_N"
for e in $BE_FILES; do IFS=: read -r p o n <<< "$e"; [ "$(m8 "$HERE/be/$p")" = "$n" ] || stop "kit: be/$p is $(m8 "$HERE/be/$p"), not $n"; done
[ "$DRY" = 1 ] || [ -n "$PATCH_NEW" ] || stop "PATCH_NEW is not given (take it from the dry run)"
if [ "$DRY" = 1 ]; then
    [ "$K" = "$HOME/src/KytyPlus" ] && stop "DRY=1 runs on a copy of the tree only (INT_K)"
    [ "$B" = "$W/d19/export/backend" ] && stop "DRY=1 runs on a copy of the backend source only (INT_B)"
    [ "$X" = "$W/exp0442/swap" ] && stop "DRY=1 keeps its copies apart (X)"
fi
[ -e "$B/.git" ] && stop "$B is a git checkout"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is $(tdiff), not $PIN_OLD"
for e in $HOST_FILES; do IFS=: read -r p o n f <<< "$e"; [ "$(m8 "$K/$p")" = "$o" ] || stop "the tree's $p is $(m8 "$K/$p"), not $o"; done
[ -e "$K/$ADD_P" ] && stop "the tree already has $ADD_P"
for e in $BE_FILES $BE_GONE; do IFS=: read -r p o n <<< "$e"; [ "$(m8 "$B/$p")" = "$o" ] || stop "the backend's $p is $(m8 "$B/$p"), not $o"; done
cache() { sed -n "s/^$2:[A-Z]*=//p" "$1/CMakeCache.txt" | head -1; }
same() { [ -n "$1" ] && [ "$(realpath -m "$1")" = "$(realpath -m "$2")" ]; }
same "$(cache "$BB" CMAKE_HOME_DIRECTORY)" "$W/d19/export/backend" || stop "backend-ubuntu is not built from $W/d19/export/backend"
[ "$(cache "$BB" BC5_BUILD_TESTS)" = OFF ] || stop "backend-ubuntu builds the tests (BC5_BUILD_TESTS is not OFF)"
for d in kytyplus-build kytyplus-build-lean; do
    same "$(cache "$W/$d" KYTY_BC5_BACKEND_SRC)" "$W/d19/export/backend" && same "$(cache "$W/$d" KYTY_BC5_BACKEND_BUILD)" "$BB" || stop "$d does not read the backend from $W/d19/export/backend and $BB"
done
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
for v in normal lean; do [ -s "$PRIV/$v/strings.txt" ] && [ -s "$PRIV/$v/strings-shared.txt" ] || stop "box0442b.sh's private build ($PRIV/$v) is missing"; done
# 2
if [ "$DRY" != 1 ]; then
    if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$W/BOX-LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then
        . "$N/chainlock0417.inc"; chain_release() { :; }; echo "the lock line of the caller is taken over: $CHAIN_LOCKLINE"
    else
        . "$N/chainlock0417.inc"
        chain_claim "exp 0442: shared swap, bake442 (bake 1: the 28 rows for every title, nothing learned, the zero list gone), patch $PIN_OLD -> $PATCH_NEW; archive, normal and lean rebuilt (CPU only, no emulator)" 90 || stop "no lock"
        trap chain_release EXIT
    fi
fi
[ -e "$X/pins.before-0442" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/host" "$X/be" || stop "cannot make $X"
if [ "$DRY" != 1 ]; then
    cp -p "$NB" "$X/kyty_emulator.normal.before-0442" && cp -p "$LB" "$X/kyty_emulator.lean.before-0442" && cp -p "$ARCH" "$X/libbc5_backend.a.before-0442" || stop "cannot copy the binaries or the archive"
fi
: > "$X/host.md5"; : > "$X/be.md5"
for e in $HOST_FILES; do IFS=: read -r p o n f <<< "$e"; mkdir -p "$X/host/$(dirname "$p")" && cp -p "$K/$p" "$X/host/$p" && (cd "$K" && md5sum "$p") >> "$X/host.md5" || stop "cannot copy $p"; done
for e in $BE_FILES $BE_GONE; do IFS=: read -r p o n <<< "$e"; mkdir -p "$X/be/$(dirname "$p")" && cp -p "$B/$p" "$X/be/$p" && (cd "$B" && md5sum "$p") >> "$X/be.md5" || stop "cannot copy $p"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0442.patch" || stop "cannot save the patch"
{ echo "PIN_OLD=$PIN_OLD"; echo "ARCH_OLD=$ARCH_OLD"; echo "ADD_P=$ADD_P"
  if [ "$DRY" != 1 ]; then echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; fi; } > "$X/pins.before-0442"
[ "$(m8 "$X/0001.before-0442.patch")" = "$PIN_OLD" ] && (cd "$X/host" && md5sum -c --quiet "$X/host.md5") && (cd "$X/be" && md5sum -c --quiet "$X/be.md5") || stop "the copies do not read back"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0442")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0442")" = "$LEAN_OLD" ] \
        && [ "$(m8 "$X/libbc5_backend.a.before-0442")" = "$ARCH_OLD" ] || stop "the binary copies do not read back"
    for v in normal lean; do nice -n 19 strings "$X/kyty_emulator.$v.before-0442" > "$X/strings-$v.before"; done
fi
echo "before: $(tr '\n' ' ' < "$X/pins.before-0442")"
# 3
for e in $HOST_FILES; do IFS=: read -r p o n f <<< "$e"; cp "$HERE/host/$f" "$K/$p" || undo "cannot install $p"; done
cp "$HERE/host/$ADD_F" "$K/$ADD_P" && git -C "$K" add -- "$ADD_P" || undo "cannot add $ADD_P"
for e in $BE_FILES; do IFS=: read -r p o n <<< "$e"; cp "$HERE/be/$p" "$B/$p" || undo "cannot install the backend's $p"; done
for e in $BE_GONE; do IFS=: read -r p o n <<< "$e"; rm -f "$B/$p" || undo "cannot remove the backend's $p"; done
for e in $HOST_FILES; do IFS=: read -r p o n f <<< "$e"; [ "$(m8 "$K/$p")" = "$n" ] || undo "$p is $(m8 "$K/$p") after the copy, not $n"; done
[ "$(m8 "$K/$ADD_P")" = "$ADD_N" ] || undo "$ADD_P does not read back"
for e in $BE_FILES; do IFS=: read -r p o n <<< "$e"; [ "$(m8 "$B/$p")" = "$n" ] || undo "the backend's $p is $(m8 "$B/$p"), not $n"; done
for e in $BE_GONE; do IFS=: read -r p o n <<< "$e"; [ -e "$B/$p" ] && undo "the backend's $p is still there"; done
P=$X/0001-new0442.patch; O=$X/0001.before-0442.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ "$( (files "$O"; echo "diff --git a/$ADD_P b/$ADD_P") | sort)" = "$(files "$P")" ] || undo "the patch's file list is not the old one + $ADD_P"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
grep '^+' "$P" | sed 's#//.*##' | grep -q '\(direct-aliases-pkg\.txt\|direct-learned\|bc5_zsk0401\|zpoll412_submit\|learned_apply\|mr412_would_learn\|guard0412_split\)' && undo  # code only: the removal comments name them (exp 0442 bake 1b dry run) "a learned file name or a learned seam is in the new patch"
for t in 'kGeneric0442' 'kGone0442' 'idraws0442.hpp' 'heap_guards_apply'; do grep -qF "$t" "$P" || undo "not in the new patch: $t"; done
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l) (+ $ADD_P), exp 0372 lines 5, pad_audio_route header in"
echo "the backend source: $(for e in $BE_FILES; do IFS=: read -r p o n <<< "$e"; printf '%s %s->%s; ' "$p" "$o" "$n"; done)gone: $(for e in $BE_GONE; do printf '%s ' "${e%%:*}"; done)"
if [ "$DRY" = 1 ]; then
    echo "swap0442 DRY: PATCH_NEW=$(m8 "$P"); the new patch is $P; undoing the copies"
    cp "$P" "$X/../0001-new0442.dry.patch" 2> /dev/null
    UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_B=$B UNDO_DRY=1 bash "$HERE/undo0442.sh"; exit $?
fi
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
# 4
echo "== $(date +%T) build the archive"
if ! distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja bc5_backend" < /dev/null > "$X/build-backend.log" 2>&1; then
    grep -m12 -E "error:" "$X/build-backend.log" | cut -c1-260; undo "the archive build failed"
fi
echo "archive: $(m8 "$ARCH"), warnings $(grep -c 'warning:' "$X/build-backend.log"); steps $(grep -c '^\[' "$X/build-backend.log")"
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260; undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
# 5
[ "$(m8 "$ARCH")" != "$ARCH_OLD" ] || undo "the archive did not change"
for f in "$ARCH" "$NB" "$LB"; do
    nice -n 19 strings "$f" | grep -q 'direct-aliases-pkg.txt\|direct-learned\|learn:' && undo "$f holds a learned file name or a learn: value"
done
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0442")" ] || undo "$v did not change"
    nice -n 19 strings "$b" > "$X/strings-$v.after"
    cmp -s <(words "$X/strings-$v.before") <(words "$PRIV/$v/strings-shared.txt") || undo "$v: the private build's reference words are not those of today's shared $v"
    g=$(line -13 "$X/strings-$v.before" "$X/strings-$v.after"); l=$(line -23 "$X/strings-$v.before" "$X/strings-$v.after")
    pg=$(line -13 "$PRIV/$v/strings-shared.txt" "$PRIV/$v/strings.txt"); pl=$(line -23 "$PRIV/$v/strings-shared.txt" "$PRIV/$v/strings.txt")
    [ $v = lean ] && [ -n "${LEAN_EXTRA_LOST:-}" ] && pl=$(printf '%s\n' $pl $LEAN_EXTRA_LOST | LC_ALL=C sort -u | tr '\n' ' ' | sed 's/ $//') # bake 1d
    echo "$v words: $(words "$X/strings-$v.before" | wc -l) -> $(words "$X/strings-$v.after" | wc -l), +[$g] -[$l]"
    [ "$g" = "$pg" ] && [ "$l" = "$pl" ] || undo "$v: words differ from the private build's: want +[$pg] -[$pl]"
    for w in $MOVED; do grep -qx "$w" "$X/strings-$v.after" || undo "$v lacks $w"; done
    grep -q 'TITLE1B' "$X/strings-$v.after" || undo "$v lacks the overlay's TITLE1B"
done
echo "swap0442 done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0442.sh (to $PIN_OLD; further back: bash $W/exp0438/bake438bkit/undo0438b.sh)"
