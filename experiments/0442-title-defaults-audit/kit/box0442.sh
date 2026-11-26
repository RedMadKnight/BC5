#!/usr/bin/env bash
# BC5 experiment 0442 (tag tg442): the PRIVATE build of the move (D26, F896). CPU only, nice 19 + ionice idle, NO lock
# line, but it refuses to start while BOX-LOCK holds a line or an emulator runs, and stops between steps when a claim
# appears. Exp 0438's way (build0438.py 3fe0aaca, ~/bc5-work/exp0438/bake438bkit): the shared builds' own compile
# commands for private copies of the changed units, the shared link with those objects swapped in; nothing shared is
# written.
#   1. pins: patch 589ef163 (the tree's diff), normal 30546370, lean 05fd749d, archive a548a249; the tree's
#      switch_defaults.hpp 48ae1cd6, bc5LleAgc.cpp ed489aca, settingsOverlay.cpp 0acb8d6b, main.cpp 6b8e4411; the
#      backend source (d19/export/backend) direct.cpp 1b8b55ec; the kit's files as mk0442.py writes them
#   2. the backend: the shared direct.cpp compiled here must give the shared archive's member byte for byte; then the
#      kit's direct.cpp (SHADOW_LABELS through env_on) into a private copy of the archive
#   3. normal and lean: src/main.cpp (for the new switch_defaults.hpp), src/libs/bc5LleAgc.cpp (+ bc5/idraws0442.hpp),
#      src/graphics/presentation/settingsOverlay.cpp, linked with the private archive
#   4. strings: no word gained in either binary against the shared one, none lost but BC5_GUARD_LEARN_LOG (dead); "kGeneric0442" is not a string, so the
#      check is the 28 moved words still present, and normal/lean each hold "TITLE1B" (the overlay compare)
#   5. the shared state pinned again after
# usage (on the box, in ~/bc5-work/exp0442/kit): bash box0442.sh
# Beside this script: build0438.py, and mk0442.py's output in new/ (switch_defaults.hpp 3e951438, bc5LleAgc.cpp 53106d30,
# settingsOverlay.cpp b7757f72, direct.cpp 63656591, idraws0442.hpp 4254c562).
# Output: ~/bc5-work/exp0442/priv/{normal,lean}/kyty_emulator, .../backend/libbc5_backend.a, .../raw/.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0442/priv; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd); N=$HERE/new
TREE=$HOME/src/KytyPlus; BTREE=$W/d19/export/backend; BBUILD=$W/backend-ubuntu; SA=$BBUILD/libbc5_backend.a
P_PATCH=589ef163; P_NORMAL=30546370; P_LEAN=05fd749d; P_ARCH=a548a249; P_SWD=48ae1cd6; P_UNIT=ed489aca; P_OVL=0acb8d6b; P_MAIN=6b8e4411; P_BE=1b8b55ec
N_SWD=3e951438; N_UNIT=53106d30; N_OVL=b7757f72; N_BE=63656591; N_ID=4254c562; K_PY=3fe0aaca
MOVED="KYTY_BC5_SAVEDATA_MEMORY_FIXES KYTY_BC5_SAVEDATA_DELETE_BUSY KYTY_BC5_SAVEDATA_ALIASES KYTY_BC5_HTTP2_FIXES KYTY_BC5_PAD_OPEN_EXT
KYTY_BC5_JSON2_FIXES KYTY_BC5_ULT_FIXES KYTY_BC5_USERSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000
KYTY_BC5_AUDIOOUT_CHECKS KYTY_BC5_AUDIOIN_CHECKS KYTY_BC5_NGS2_RACK_FIX KYTY_BC5_FW_PAD KYTY_BC5_LOAD_ZLIB KYTY_BC5_LOAD_JPEG
KYTY_BC5_LOAD_IME KYTY_BC5_LOAD_NPCOMMON KYTY_BC5_LOAD_NPMANAGER KYTY_BC5_LOAD_NPTROPHY BC5_DIRECT_MEC_INDIRECT
BC5_DIRECT_REMEMBER_UNMAPPED KYTY_BC5_APR_PARALLEL BC5_DIRECT_GPU_CHECK BC5_DIRECT_DMA_SNAPSHOT BC5_DIRECT_CS_PREFIX
BC5_DIRECT_INDIRECT_DRAWS BC5_DIRECT_LAZY_RELEASE"
NICE="nice -n 19 ionice -c 3"
stop() { echo "box0442 STOP: $*"; exit 1; }
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
free_box() { # no lock line and no emulator (exp 0442 holds no lock: a CPU build steps aside)
    [ -s "$W/BOX-LOCK" ] && stop "BOX-LOCK holds a line: $(cat "$W/BOX-LOCK")"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    return 0
}
shared() {
    echo "patch $(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8) normal $(m8 "$W/kytyplus-build/src/kyty_emulator") lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m8 "$SA") swd $(m8 "$TREE/src/bc5/switch_defaults.hpp") unit $(m8 "$TREE/src/libs/bc5LleAgc.cpp") ovl $(m8 "$TREE/src/graphics/presentation/settingsOverlay.cpp") main $(m8 "$TREE/src/main.cpp") be $(m8 "$BTREE/src/direct.cpp")"
}
want="patch $P_PATCH normal $P_NORMAL lean $P_LEAN archive $P_ARCH swd $P_SWD unit $P_UNIT ovl $P_OVL main $P_MAIN be $P_BE"
free_box
before=$(shared); echo "shared before: $before"
[ "$before" = "$want" ] || stop "the shared state is not the base: want [$want]"
[ "$(m8 "$N/switch_defaults.hpp")" = "$N_SWD" ] && [ "$(m8 "$N/bc5LleAgc.cpp")" = "$N_UNIT" ] && [ "$(m8 "$N/settingsOverlay.cpp")" = "$N_OVL" ] \
    && [ "$(m8 "$N/direct.cpp")" = "$N_BE" ] && [ "$(m8 "$N/idraws0442.hpp")" = "$N_ID" ] && [ "$(m8 "$HERE/build0438.py")" = "$K_PY" ] \
    || stop "the kit's files are not mk0442.py's output (or build0438.py is not $K_PY)"
mkdir -p "$R" || stop "mkdir $R"
rm -rf "$S"; mkdir -p "$S/kyty/src/bc5" "$S/kyty/src/libs" "$S/kyty/src/graphics/presentation" "$S/backend/src" "$S/ref/src" "$E/backend" "$E/backend-ref" || stop "mkdir $S"
cp "$TREE/src/main.cpp" "$S/kyty/src/" && cp "$N/switch_defaults.hpp" "$N/idraws0442.hpp" "$S/kyty/src/bc5/" && cp "$N/bc5LleAgc.cpp" "$S/kyty/src/libs/" \
    && cp "$N/settingsOverlay.cpp" "$S/kyty/src/graphics/presentation/" && cp "$N/direct.cpp" "$S/backend/src/" && cp "$BTREE/src/direct.cpp" "$S/ref/src/" \
    || stop "copy the kit"
(cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
# 2. the backend
free_box
distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
rm -rf "$E/backend-ref/"*
distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD" \
    "$SA" "$E/backend-ref/libbc5_backend.a" src/direct.cpp > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
distrobox enter ubuntu -- sh -c "cd '$E/backend-ref' && ar p '$SA' direct.cpp.o > shared-direct.o && ar p libbc5_backend.a direct.cpp.o > ref-direct.o" < /dev/null || stop "ar p"
cmp -s "$E/backend-ref/shared-direct.o" "$E/backend-ref/ref-direct.o" || stop "the reference direct.cpp.o is not the shared archive's member"
echo "reference: direct.cpp.o of $P_BE compiled here == the shared archive's member ($(m8 "$E/backend-ref/ref-direct.o"))"
rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
    "$SA" "$E/backend/libbc5_backend.a" src/direct.cpp > "$R/build-backend.out" 2>&1 < /dev/null || { tail -40 "$R/build-backend.out"; stop "the private archive failed"; }
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
        "ARCHIVE=$E/backend/libbc5_backend.a" src/main.cpp src/libs/bc5LleAgc.cpp src/graphics/presentation/settingsOverlay.cpp > "$R/build-$v.out" 2>&1 < /dev/null
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
    # BC5_GUARD_LEARN_LOG: its only reader is in alias_learn(), which is never called, so the deleted table row was the
    # word's last live use and the compiler drops the string (the audit's finding 4)
    [ -z "$gained" ] && { [ -z "$lost" ] || [ "$lost" = BC5_GUARD_LEARN_LOG ]; } || stop "$v: words changed"
    for w in $MOVED; do grep -qx "$w" "$E/$v/strings.txt" || stop "$v lacks $w"; done
    grep -q 'TITLE1B' "$E/$v/strings.txt" || stop "$v lacks the overlay's TITLE1B"
    grep -q '^TITLE1$' "$E/$v/strings.txt" && stop "$v still holds the bare TITLE1 compare string"
done
echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), archive $(cut -c1-8 "$E/backend/archive.md5")"
# 5.
[ "$(shared)" = "$before" ] || stop "the shared state changed: $(shared)"
echo "shared after: $(shared): unchanged"
