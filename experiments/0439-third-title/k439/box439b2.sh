#!/usr/bin/env bash
# BC5 exp 0439 bake 2 (tag b2439): the private build of the bake-2 kit, on top of bake 1 once bake 1 is the shared state
# (exp 0442's swap). CPU only, nice 19 + ionice idle, NO lock line; it refuses to start while BOX-LOCK holds a line, a
# b439*/b0442* unit is active or an emulator runs, and it stops between steps when one appears. Nothing shared is written.
#   1. pins: the shared state (BASE_PINS, set by the caller from bake 1's swap record: patch, normal, lean, archive and
#      the tree's units) and the kit's inputs: new/ = mkb2439.py's output (bc5LleAgc.cpp, videoOut.cpp,
#      switch_defaults.hpp, dc0439.hpp, cw0439.hpp) + mkdm439b.py's (ajm.cpp, atrac9_decoder.h, dm0439.hpp), be/ =
#      b2be439.py's output (src/direct.cpp, src/full_state.cpp, src/policy.cpp, include/bc5/ib_chain.hpp, ds0439.hpp)
#   2. the backend: the shared units compiled here must equal the shared archive's members; then the kit's three into a
#      private copy of the archive (build0438.py archive)
#   3. normal and lean: bc5LleAgc.cpp, videoOut.cpp, ajm.cpp (with the headers on the include path), linked with it
#   4. strings: the words gained must be bake 2's (the list below), none lost; the lean word count before and after
#   5. the shared state pinned again after
# usage (on the box, in ~/bc5-work/exp0439/b2, on the top session's word):
#   BASE_PINS="patch <p> normal <n> lean <l> archive <a> swd <h> unit <u> vout <v> ajm <j> a9 <d>" NEW_PINS="..." BE_PINS="..." bash box439b2.sh
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0439/b2/priv; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd); N=$HERE/new; B=$HERE/be
# 11-24 night (vz439): B2_HOST=1 builds on the host with the shared builds' own toolchain (~/bc5-toolchain, since the host-native
# rebuild of 17:15-17:23); the default stays the ubuntu distrobox
if [ "${B2_HOST:-0}" = 1 ]; then DBX="env PATH=$HOME/bc5-toolchain/bin:$PATH"; else DBX="distrobox enter ubuntu --"; fi
TREE=$HOME/src/KytyPlus; BTREE=$W/d19/export/backend; BBUILD=$W/backend-ubuntu; SA=$BBUILD/libbc5_backend.a
BASE_PINS=${BASE_PINS:?"the shared state after bake 1's swap (its swap record), as shared() prints it"}
NEW_PINS=${NEW_PINS:?"new/'s md5s, name=md5 each, from the laptop's kit run"}
BE_PINS=${BE_PINS:?"be/'s md5s, path=md5 each"}
UNITS_BE=${UNITS_BE:-"src/direct.cpp src/full_state.cpp src/policy.cpp"} # 11-24 (tag cs439): + src/state_stack.cpp when the kit carries it
UNITS_KY="src/libs/bc5LleAgc.cpp src/graphics/presentation/videoOut.cpp src/libs/ajm.cpp src/main.cpp src/kernel/pthread.cpp src/libs/libAmpr.cpp src/graphics/presentation/window/window.cpp"
# exp 0439 (tag wt439): window.cpp from mkwt439.py, the window title without the frame rate (the maintainer, 11-22)
# exp 0439 (11-22 night, tag b2fix): switch_defaults.hpp is included by main.cpp (which applies the tables at process start),
# kernel/pthread.cpp and libs/libAmpr.cpp; built without them the executable kept the OLD tables and none of bake 2's rows
# took effect (d2r1/d2r2: PREFIX_CHAINS=0, CHAIN_WRITERS=0, AT9_DMC unset -> the title's Scream divide, F892). They are
# compiled here from new/ (tree copies; libAmpr.cpp with ap439 when the kit has it).
# exp 0439 (11-22 night, the diagnosis build on bake 2): EXTRA_KY="src/libs/libAmpr.cpp src/libs/libVideoDec2.cpp" adds
# units (from new/ by their file name); EXTRA_GAINED adds words the strings check accepts; E_DIR moves the output (a
# diagnosis build must not overwrite bake 2's own private build). All empty for the bake itself.
UNITS_KY="$UNITS_KY ${EXTRA_KY:-}"
[ -n "${E_DIR:-}" ] && E=$E_DIR R=$E_DIR/raw S=$E_DIR/src
GAINED="BC5_DIRECT_PREFIX_CHAINS BC5_DIRECT_CHAIN_WRITERS BC5_DIRECT_WAIT_MS BC5_DIRECT_DMA_SYNC_MEC BC5_DIRECT_DMA_SYNC_LABEL KYTY_BC5_AT9_DMC BC5_DIRECT_FLAT_APERTURE_PIECES
BC5_DIRECT_IB_CHAIN BC5_DIRECT_IB_CHAIN_FLAT BC5_DIRECT_AGC_EOP_IDENT BC5_DIRECT_EAGER_GPU_WRITE BC5_DIRECT_DCC_PRESENT"
NICE="nice -n 19 ionice -c 3"
stop() { echo "box439b2 STOP: $*"; exit 1; }
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
free_box() {
    [ -s "$W/BOX-LOCK" ] && stop "BOX-LOCK holds a line: $(cat "$W/BOX-LOCK")"
    systemctl --user list-units --state=active --no-legend 'b439*' 'b0442*' 2> /dev/null | grep -q . && stop "a build unit is active"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    return 0
}
shared() {
    echo "patch $(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8) normal $(m8 "$W/kytyplus-build/src/kyty_emulator") lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m8 "$SA") swd $(m8 "$TREE/src/bc5/switch_defaults.hpp") unit $(m8 "$TREE/src/libs/bc5LleAgc.cpp") vout $(m8 "$TREE/src/graphics/presentation/videoOut.cpp") ajm $(m8 "$TREE/src/libs/ajm.cpp") a9 $(m8 "$TREE/src/libs/ajm/atrac9_decoder.h")"
}
free_box
before=$(shared); echo "shared before: $before"
[ "$before" = "$BASE_PINS" ] || stop "the shared state is not bake 1's: want [$BASE_PINS]"
for p in $NEW_PINS; do [ "$(m8 "$N/${p%%=*}")" = "${p#*=}" ] || stop "new/${p%%=*} is $(m8 "$N/${p%%=*}"), not ${p#*=}"; done
for p in $BE_PINS; do [ "$(m8 "$B/${p%%=*}")" = "${p#*=}" ] || stop "be/${p%%=*} is $(m8 "$B/${p%%=*}"), not ${p#*=}"; done
[ -f "$HERE/build0438.py" ] || stop "build0438.py is not beside this script"
mkdir -p "$R" || stop "mkdir $R"
rm -rf "$S"; mkdir -p "$S/kyty/src/bc5" "$S/kyty/src/libs/ajm" "$S/kyty/src/graphics/presentation" "$S/backend/src" "$S/backend/include/bc5" "$S/ref/src" "$E/backend" "$E/backend-ref" || stop "mkdir $S"
cp "$N/switch_defaults.hpp" "$N/dc0439.hpp" "$N/cw0439.hpp" "$N/fp0439.hpp" "$N/dm0439.hpp" "$B/include/bc5/ib_chain.hpp" "$S/kyty/src/bc5/" \
    && cp "$BTREE/include/bc5/state_stack.hpp" "$S/kyty/src/bc5/" \
    && cp "$N/bc5LleAgc.cpp" "$N/ajm.cpp" "$S/kyty/src/libs/" && cp "$N/atrac9_decoder.h" "$S/kyty/src/libs/ajm/" \
    && cp "$N/videoOut.cpp" "$S/kyty/src/graphics/presentation/" \
    && mkdir -p "$S/kyty/src/graphics/presentation/window" && cp "$N/window.cpp" "$S/kyty/src/graphics/presentation/window/window.cpp" \
    && mkdir -p "$S/kyty/src/kernel" && cp "$N/main.cpp" "$S/kyty/src/main.cpp" && cp "$N/pthread.cpp" "$S/kyty/src/kernel/pthread.cpp" && cp "$N/libAmpr.cpp" "$S/kyty/src/libs/libAmpr.cpp" \
    && for u in ${EXTRA_KY:-}; do cp "$N/$(basename "$u")" "$S/kyty/$u" || exit 1; done \
    && { [ ! -f "$N/tc0439.hpp" ] || cp "$N/tc0439.hpp" "$S/kyty/src/bc5/"; } \
    && { [ ! -f "$N/sr0439b.hpp" ] || cp "$N/sr0439b.hpp" "$S/kyty/src/bc5/"; } \
    && { [ ! -f "$N/vf0439.hpp" ] || cp "$N/vf0439.hpp" "$S/kyty/src/bc5/"; } \
    && { [ ! -f "$N/pw0439.hpp" ] || cp "$N/pw0439.hpp" "$S/kyty/src/bc5/"; }     && { [ ! -f "$N/sr0439c.hpp" ] || cp "$N/sr0439c.hpp" "$S/kyty/src/bc5/"; } && { [ ! -f "$N/f4p0439.hpp" ] || cp "$N/f4p0439.hpp" "$S/kyty/src/bc5/"; } \
    && cp "$B/src/direct.cpp" "$B/src/full_state.cpp" "$B/src/policy.cpp" "$S/backend/src/" && cp "$B/include/bc5/ib_chain.hpp" "$B/include/bc5/ds0439.hpp" "$S/backend/include/bc5/" \
    && { [ ! -f "$B/include/bc5/pw0439.hpp" ] || cp "$B/include/bc5/pw0439.hpp" "$S/backend/include/bc5/"; } \
    && { [ ! -f "$B/include/bc5/dk0439.hpp" ] || cp "$B/include/bc5/dk0439.hpp" "$S/backend/include/bc5/"; }     && { [ ! -f "$B/include/bc5/sr0439c.hpp" ] || cp "$B/include/bc5/sr0439c.hpp" "$S/backend/include/bc5/"; } \
    && { [ ! -f "$B/src/state_stack.cpp" ] || cp "$B/src/state_stack.cpp" "$S/backend/src/"; } && { [ ! -f "$B/include/bc5/cs0439.hpp" ] || cp "$B/include/bc5/cs0439.hpp" "$S/backend/include/bc5/"; } \
    && for u in $UNITS_BE; do cp "$BTREE/$u" "$S/ref/src/"; done || stop "copy the kit"
(cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
# 2. the backend
free_box
$DBX sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
rm -rf "$E/backend-ref/"*
# shellcheck disable=SC2086
$DBX $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD" \
    "$SA" "$E/backend-ref/libbc5_backend.a" $UNITS_BE > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
for u in $UNITS_BE; do
    o=$(basename "$u").o
    $DBX sh -c "cd '$E/backend-ref' && ar p '$SA' $o > shared-$o && ar p libbc5_backend.a $o > ref-$o" < /dev/null || stop "ar p $o"
    cmp -s "$E/backend-ref/shared-$o" "$E/backend-ref/ref-$o" || stop "the reference $o is not the shared archive's member"
    echo "reference: $o compiled here == the shared archive's member ($(m8 "$E/backend-ref/ref-$o"))"
done
rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
# shellcheck disable=SC2086
$DBX $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
    "$SA" "$E/backend/libbc5_backend.a" $UNITS_BE > "$R/build-backend.out" 2>&1 < /dev/null || { tail -40 "$R/build-backend.out"; stop "the private archive failed"; }
echo "private archive $(m8 "$E/backend/libbc5_backend.a"): errors $(grep -c 'error:' "$R/build-backend.out"), warnings $(grep -c 'warning:' "$R/build-backend.out")"
m8 "$E/backend/libbc5_backend.a" > "$E/backend/archive.md5"
# 3. normal and lean
for v in normal lean; do
    free_box
    b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
    mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    $DBX sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
    # shellcheck disable=SC2086
    $DBX $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
        "ARCHIVE=$E/backend/libbc5_backend.a" $UNITS_KY > "$R/build-$v.out" 2>&1 < /dev/null
    rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
    grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
    m8 "$bin" > "$E/$v/binary.md5"
    nice -n 19 strings "$bin" > "$E/$v/strings.txt"
    nice -n 19 strings "$b/src/kyty_emulator" > "$E/$v/strings-shared.txt"
done
# 4. strings: the words gained are bake 2's, none lost; the lean count before and after
for v in normal lean; do
    gained=$(comm -13 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
    lost=$(comm -23 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
    echo "$v $(cut -c1-8 "$E/$v/binary.md5"): words $(words "$E/$v/strings-shared.txt" | wc -l) -> $(words "$E/$v/strings.txt" | wc -l), +[$gained] -[$lost]"
    for w in $gained; do case " $(echo $GAINED ${EXTRA_GAINED:-}) " in *" $w "*) ;; *) stop "$v gained $w, which is not bake 2's" ;; esac; done
    [ -z "$lost" ] || stop "$v lost words: $lost"
    grep -q 'tag pa439\|tag gp439\|tag un439\|tag rs439\|ms439-trigger' "$E/$v/strings.txt" && stop "$v holds a probe of the diagnosis build"
done
echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), archive $(cut -c1-8 "$E/backend/archive.md5")"
# 5.
[ "$(shared)" = "$before" ] || stop "the shared state changed: $(shared)"
echo "shared after: $(shared): unchanged"
