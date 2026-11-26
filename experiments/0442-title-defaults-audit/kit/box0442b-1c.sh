#!/usr/bin/env bash
# BC5 experiment 0442, second private build (tags tg442 + nl442 + the count modes): box0442.sh (the first build, normal
# 3079cdf9, lean fa07ceb9) with the learned artefacts removed (the top session's decision of 2026-11-22: the aliases and
# their file, GUARD_SPLIT, GUARD_LEARN_LOG and alias_learn, HOST_INDIRECT whole, exp 0379's zero list whole (zl442), the
# renames of rn442 (learned_apply -> heap_guards_apply, mr412_would_learn -> mr412_fault_record, load_stat names), the zero skip's learned-window guard and
# seam, the m11 learn refusal; the gone words reported and unset by kGone0442) and the count modes of GPU_CHECK_PRODUCT and
# SHADOW_LABELS. CPU only, nice 19 + ionice idle, NO lock line; refuses to start while BOX-LOCK holds a line or an emulator
# runs, and stops between steps when one appears. Nothing shared is written.
#   1. pins: the shared state as box0442.sh (patch 589ef163, normal 30546370, lean 05fd749d, archive a548a249, the tree's
#      units) and the shared backend sources (d19/export/backend = main's): direct.cpp 1b8b55ec, indirect_check.cpp
#      6c0adc0a, shadow_labels.cpp 2cfbea8b; the kit's files: mk0442.py's output in new/, the branch's backend files in be/
#   2. the backend: the three shared units compiled here must give the shared archive's members byte for byte; then the
#      branch's three into a private copy of the archive (host_indirect.cpp.o stays in it, referenced by nothing)
#   3. normal and lean: src/main.cpp, src/libs/bc5LleAgc.cpp (+ bc5/idraws0442.hpp), settingsOverlay.cpp, and the seven other
#      units that include bc5/load_stat.hpp (renamed names; unchanged copies of the tree's units), with the
#      branch's bc5/direct.hpp shadowing the backend's (map_alias and unmap_aliases are gone), linked with the private archive
#   4. strings: words gained only among kGone0442's names (they are now strings of the table), lost only words of the
#      zero list's family (ZERO, ZSKIP, ZSCAN, PIN_CAP); the 28 moved
#      words present; TITLE1B present; no "direct-aliases-pkg.txt", "direct-learned" or "learn:" text anywhere
#   5. the shared state pinned again after
# usage (on the box, in ~/bc5-work/exp0442/kit, on the top session's word): bash box0442b.sh
# Beside this script: build0438.py (3fe0aaca); new/ = mk0442.py's output (switch_defaults.hpp 77fa88cd with MK0442_KEEP=<the five G6+G7 rows> MK0442_LEAN_GONE_OUT=1, bake 1b; bca8a81f bake 1a; 3f9ee1d9 without, bc5LleAgc.cpp
# 3b28b024, settingsOverlay.cpp b7757f72, load_stat.hpp 8e401e5f, idraws0442.hpp 4254c562); be/ = the branch's backend/ files (src/direct.cpp,
# src/indirect_check.cpp, src/shadow_labels.cpp, include/bc5/{direct,indirect_check,shadow_labels}.hpp), md5s in BE_PINS.
# Output: ~/bc5-work/exp0442/priv4/{normal,lean}/kyty_emulator, .../backend/libbc5_backend.a, .../raw/.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0442/priv5; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd); N=$HERE/new; B=$HERE/be
TREE=$HOME/src/KytyPlus; BTREE=$W/d19/export/backend; BBUILD=$W/backend-ubuntu; SA=$BBUILD/libbc5_backend.a
P_PATCH=589ef163; P_NORMAL=30546370; P_LEAN=05fd749d; P_ARCH=a548a249; P_SWD=48ae1cd6; P_UNIT=ed489aca; P_OVL=0acb8d6b; P_MAIN=6b8e4411; P_LS=e4090056
LS_UNITS="src/kernel/fileSystem.cpp src/kernel/memory.cpp src/kernel/pthread.cpp src/kernel/semaphore.cpp src/libs/controller.cpp src/libs/libAmpr.cpp src/libs/network.cpp"
P_BE="src/direct.cpp=1b8b55ec src/indirect_check.cpp=6c0adc0a src/shadow_labels.cpp=2cfbea8b"
N_SWD=e2469a63; N_UNIT=4857668e; N_OVL=b7757f72; N_ID=4254c562; N_LS=8e401e5f; K_PY=3fe0aaca
BE_PINS=${BE_PINS:?"the md5s of be/'s six files, as git rev-parse's commit has them (set by the caller from the branch)"}
UNITS_BE="src/direct.cpp src/indirect_check.cpp src/shadow_labels.cpp"
GONE="BC5_DIRECT_ALIASES BC5_GUARD_SPLIT BC5_GUARD_LEARN_LOG BC5_DIRECT_HOST_INDIRECT BC5_DIRECT_LEARNED BC5_DIRECT_LEARN_GUEST_ONLY"
MOVED="KYTY_BC5_SAVEDATA_MEMORY_FIXES KYTY_BC5_SAVEDATA_DELETE_BUSY KYTY_BC5_SAVEDATA_ALIASES KYTY_BC5_HTTP2_FIXES KYTY_BC5_PAD_OPEN_EXT
KYTY_BC5_JSON2_FIXES KYTY_BC5_ULT_FIXES KYTY_BC5_USERSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000
KYTY_BC5_AUDIOOUT_CHECKS KYTY_BC5_AUDIOIN_CHECKS KYTY_BC5_NGS2_RACK_FIX KYTY_BC5_FW_PAD KYTY_BC5_LOAD_ZLIB KYTY_BC5_LOAD_JPEG
KYTY_BC5_LOAD_IME KYTY_BC5_LOAD_NPCOMMON KYTY_BC5_LOAD_NPMANAGER KYTY_BC5_LOAD_NPTROPHY BC5_DIRECT_MEC_INDIRECT
BC5_DIRECT_REMEMBER_UNMAPPED KYTY_BC5_APR_PARALLEL BC5_DIRECT_GPU_CHECK BC5_DIRECT_DMA_SNAPSHOT BC5_DIRECT_CS_PREFIX
BC5_DIRECT_INDIRECT_DRAWS BC5_DIRECT_LAZY_RELEASE"
NICE="nice -n 19 ionice -c 3"
stop() { echo "box0442b STOP: $*"; exit 1; }
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
free_box() {
    [ -s "$W/BOX-LOCK" ] && stop "BOX-LOCK holds a line: $(cat "$W/BOX-LOCK")"
    systemctl --user list-units --state=active --no-legend 'b439*' 2> /dev/null | grep -q . && stop "an exp 0439 unit (b439*) is active"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    return 0
}
shared() {
    local be="" p
    for p in $P_BE; do be="$be ${p%%=*}=$(m8 "$BTREE/${p%%=*}")"; done
    echo "patch $(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8) normal $(m8 "$W/kytyplus-build/src/kyty_emulator") lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m8 "$SA") swd $(m8 "$TREE/src/bc5/switch_defaults.hpp") ls $(m8 "$TREE/src/bc5/load_stat.hpp") unit $(m8 "$TREE/src/libs/bc5LleAgc.cpp") ovl $(m8 "$TREE/src/graphics/presentation/settingsOverlay.cpp") main $(m8 "$TREE/src/main.cpp") be$be"
}
want="patch $P_PATCH normal $P_NORMAL lean $P_LEAN archive $P_ARCH swd $P_SWD ls $P_LS unit $P_UNIT ovl $P_OVL main $P_MAIN be $P_BE"
free_box
before=$(shared); echo "shared before: $before"
[ "$before" = "$want" ] || stop "the shared state is not the base: want [$want]"
[ "$(m8 "$N/switch_defaults.hpp")" = "$N_SWD" ] && [ "$(m8 "$N/bc5LleAgc.cpp")" = "$N_UNIT" ] && [ "$(m8 "$N/settingsOverlay.cpp")" = "$N_OVL" ] \
    && [ "$(m8 "$N/idraws0442.hpp")" = "$N_ID" ] && [ "$(m8 "$N/load_stat.hpp")" = "$N_LS" ] && [ "$(m8 "$HERE/build0438.py")" = "$K_PY" ] \
    || stop "new/ is not mk0442.py's output (or build0438.py is not $K_PY)"
for p in $BE_PINS; do [ "$(m8 "$B/${p%%=*}")" = "${p#*=}" ] || stop "be/${p%%=*} is $(m8 "$B/${p%%=*}"), not ${p#*=}"; done
mkdir -p "$R" || stop "mkdir $R"
rm -rf "$S"; mkdir -p "$S/kyty/src/bc5" "$S/kyty/src/libs" "$S/kyty/src/kernel" "$S/kyty/src/graphics/presentation" "$S/backend" "$S/ref/src" "$E/backend" "$E/backend-ref" || stop "mkdir $S"
cp "$TREE/src/main.cpp" "$S/kyty/src/" && cp "$N/switch_defaults.hpp" "$N/idraws0442.hpp" "$N/load_stat.hpp" "$B/include/bc5/direct.hpp" "$S/kyty/src/bc5/" \
    && for u in $LS_UNITS; do cp "$TREE/$u" "$S/kyty/$u" || exit 1; done \
    && cp "$N/bc5LleAgc.cpp" "$S/kyty/src/libs/" && cp "$N/settingsOverlay.cpp" "$S/kyty/src/graphics/presentation/" \
    && cp -r "$B/src" "$B/include" "$S/backend/" && for u in $UNITS_BE; do cp "$BTREE/$u" "$S/ref/src/"; done || stop "copy the kit"
(cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
# 2. the backend
free_box
distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
rm -rf "$E/backend-ref/"*
# shellcheck disable=SC2086
distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD" \
    "$SA" "$E/backend-ref/libbc5_backend.a" $UNITS_BE > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
for u in $UNITS_BE; do
    o=$(basename "$u").o
    distrobox enter ubuntu -- sh -c "cd '$E/backend-ref' && ar p '$SA' $o > shared-$o && ar p libbc5_backend.a $o > ref-$o" < /dev/null || stop "ar p $o"
    cmp -s "$E/backend-ref/shared-$o" "$E/backend-ref/ref-$o" || stop "the reference $o is not the shared archive's member"
    echo "reference: $o compiled here == the shared archive's member ($(m8 "$E/backend-ref/ref-$o"))"
done
rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
# shellcheck disable=SC2086
distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
    "$SA" "$E/backend/libbc5_backend.a" $UNITS_BE > "$R/build-backend.out" 2>&1 < /dev/null || { tail -40 "$R/build-backend.out"; stop "the private archive failed"; }
echo "private archive $(m8 "$E/backend/libbc5_backend.a"): errors $(grep -c 'error:' "$R/build-backend.out"), warnings $(grep -c 'warning:' "$R/build-backend.out")"
m8 "$E/backend/libbc5_backend.a" > "$E/backend/archive.md5"
# 3. normal and lean
for v in normal lean; do
    free_box
    b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
    mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
        "ARCHIVE=$E/backend/libbc5_backend.a" src/main.cpp src/libs/bc5LleAgc.cpp src/graphics/presentation/settingsOverlay.cpp $LS_UNITS > "$R/build-$v.out" 2>&1 < /dev/null
    rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
    grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
    m8 "$bin" > "$E/$v/binary.md5"
    nice -n 19 strings "$bin" > "$E/$v/strings.txt"
    nice -n 19 strings "$b/src/kyty_emulator" > "$E/$v/strings-shared.txt"
done
# 4. strings
for v in normal lean; do
    gained=$(comm -13 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
    lost=$(comm -23 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
    echo "$v $(cut -c1-8 "$E/$v/binary.md5"): words $(words "$E/$v/strings-shared.txt" | wc -l) -> $(words "$E/$v/strings.txt" | wc -l), +[$gained] -[$lost]"
    for w in $gained; do case "$w" in BC5_DIRECT_0442_GC_NOCOPY|BC5_DIRECT_0442_CS_SKIP|BC5_DIRECT_0442_SNAP_GROW) ;; *) [ $v = lean ] && stop "lean gained $w: only the three bake 1c off-words may be new in lean" ;; esac; done
    gained=$(for w in $gained; do case "$w" in BC5_DIRECT_0442_*) ;; *) printf "%s " "$w" ;; esac; done)
    for w in $gained; do case " $GONE " in *" $w "*) ;; *) stop "$v gained $w, which is not one of kGone0442's names" ;; esac; done
    for w in $lost; do case "$w" in *ZERO*|*ZSKIP*|*ZSCAN*|*PIN_CAP*) ;; *) [ $v = lean ] && case " $GONE " in *" $w "*) continue ;; esac; stop "$v lost $w, which is not of the zero list's family" ;; esac; done
    for w in $MOVED; do grep -qx "$w" "$E/$v/strings.txt" || stop "$v lacks $w"; done
    grep -q 'TITLE1B' "$E/$v/strings.txt" || stop "$v lacks the overlay's TITLE1B"
    grep -q 'direct-aliases-pkg.txt\|direct-learned\|learn:' "$E/$v/strings.txt" && stop "$v holds a learned file name or a learn: value"
done
grep -q 'direct-aliases-pkg.txt\|direct-learned\|learn:' <(nice -n 19 strings "$E/backend/libbc5_backend.a") && echo "note: the private archive still holds learned text (host_indirect.cpp.o, unreferenced)"
echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), archive $(cut -c1-8 "$E/backend/archive.md5")"
# 5.
[ "$(shared)" = "$before" ] || stop "the shared state changed: $(shared)"
echo "shared after: $(shared): unchanged"
