#!/usr/bin/env bash
# BC5 experiment 0438 (tag bake438b): the PRIVATE build of the exact bake files, before the shared swap. CPU only,
# nice 19 + ionice idle, one job, NO lock line. boxa2.sh's and boxstack438.sh's way (build0438.py): the shared builds' own
# compile commands for private copies of the patched units, the shared link with those objects swapped in; nothing
# shared is written.
#   1. pins: the shared normal 199a0f39, lean 3a20b974, archive d6638808; the tree's bc5LleAgc.cpp 2e6168de, memory.cpp
#      aa7d7f5b, switch_defaults.hpp 48ae1cd6; the backend source (d19/export/backend) direct.cpp eacf8d2a, direct.hpp
#      9256f3b9, no mapping_index.hpp; the kit's files are the ones pins438b.inc names
#   2. the backend: main's direct.cpp compiled the same way must give the shared archive's member byte for byte (the
#      method's check); then the kit's direct.cpp into a private copy of the archive (direct.cpp is the only backend
#      source that includes direct.hpp, so no other member changes)
#   3. normal and lean: bc5LleAgc.cpp and memory.cpp from the kit (src/bc5/direct.hpp and mapping_index.hpp from the kit
#      shadow the backend's), linked with the private archive
#   4. strings: the private archive holds BC5_DIRECT_0438_A2 and neither BC5_DIRECT_0438_A2_CHECK nor the a2c438 /
#      MISMATCH lines; each binary against the shared one gains exactly the bake's words (normal: BC5_0438_INFLIGHT_NG
#      BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1J KYTY_BC5_0438_A1P; lean the same without A1J)
#      and loses none; no A2_CHECK in either; normal holds the ng438, wd438, a1c438 and r438o lines; lean holds none of
#      them, no A1J (leanwords438b.sh prints lean's word count before and after); no SUBMITQ / R438_LWM anywhere
#   5. the shared state pinned again after
#   boxbake438b.sh build
# Beside this script (scp'd to ~/bc5-work/exp0438/bake438bkit): pins438b.inc, build0438.py (3fe0aaca), leanwords438b.sh,
# and mkbake438b.py's OUT_DIR/new/ as it is: kyty/src/libs/bc5LleAgc.cpp, kyty/src/kernel/memory.cpp,
# backend/src/direct.cpp, backend/include/bc5/direct.hpp, backend/include/bc5/mapping_index.hpp.
# Output: ~/bc5-work/exp0438/bake438b-priv/{normal,lean}/kyty_emulator, .../backend/libbc5_backend.a, .../raw/.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438/bake438b-priv; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; BTREE=$W/d19/export/backend; BBUILD=$W/backend-ubuntu; SA=$BBUILD/libbc5_backend.a
P_NORMAL=199a0f39; P_LEAN=3a20b974; P_ARCH=d6638808; P_UNIT=2e6168de; P_MEM=aa7d7f5b; P_SWD=48ae1cd6; P_BE_CPP=eacf8d2a; P_BE_HPP=9256f3b9
K_PY=3fe0aaca
WORDS_NORMAL="BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1J KYTY_BC5_0438_A1P"
WORDS_LEAN="BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1P"
NICE="nice -n 19 ionice -c 3"
stop() { echo "bake438b-priv STOP: $*"; exit 1; }
m8() { md5sum < "$1" 2> /dev/null | cut -c1-8; }
words() { grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' "$1" | sort -u; }
shared() { # the shared state, one line
    echo "normal $(m8 "$W/kytyplus-build/src/kyty_emulator") lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m8 "$SA") unit $(m8 "$TREE/src/libs/bc5LleAgc.cpp") memory $(m8 "$TREE/src/kernel/memory.cpp") switch_defaults $(m8 "$TREE/src/bc5/switch_defaults.hpp") be-cpp $(m8 "$BTREE/src/direct.cpp") be-hpp $(m8 "$BTREE/include/bc5/direct.hpp") be-mi $([ -e "$BTREE/include/bc5/mapping_index.hpp" ] && echo present || echo absent)"
}
build() {
    local want="normal $P_NORMAL lean $P_LEAN archive $P_ARCH unit $P_UNIT memory $P_MEM switch_defaults $P_SWD be-cpp $P_BE_CPP be-hpp $P_BE_HPP be-mi absent"
    local before v b bin rc gained lost
    before=$(shared); echo "shared before: $before"
    [ "$before" = "$want" ] || stop "the shared state is not the bake's base: want [$want]"
    KIT_PATCH=; UNIT_NEW=; MEM_NEW=; BE_CPP_NEW=; BE_HPP_NEW=; BE_MI_NEW=
    . "$HERE/pins438b.inc" || stop "no pins438b.inc"
    [ "$(m8 "$HERE/kyty/src/libs/bc5LleAgc.cpp")" = "$UNIT_NEW" ] && [ "$(m8 "$HERE/kyty/src/kernel/memory.cpp")" = "$MEM_NEW" ] \
        && [ "$(m8 "$HERE/backend/src/direct.cpp")" = "$BE_CPP_NEW" ] && [ "$(m8 "$HERE/backend/include/bc5/direct.hpp")" = "$BE_HPP_NEW" ] \
        && [ "$(m8 "$HERE/backend/include/bc5/mapping_index.hpp")" = "$BE_MI_NEW" ] && [ "$(m8 "$HERE/build0438.py")" = "$K_PY" ] && [ -s "$HERE/leanwords438b.sh" ] \
        || stop "the kit's files are not the ones pins438b.inc names (unit $UNIT_NEW, memory $MEM_NEW, direct.cpp $BE_CPP_NEW, direct.hpp $BE_HPP_NEW, mapping_index $BE_MI_NEW, build0438.py $K_PY)"
    mkdir -p "$R" || stop "mkdir $R"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/kernel" "$S/kyty/src/bc5" "$S/backend/src" "$S/backend/include/bc5" "$S/ref/src" "$S/ref/include/bc5" "$E/backend" "$E/backend-ref" || stop "mkdir $S"
    cp "$HERE/kyty/src/libs/bc5LleAgc.cpp" "$S/kyty/src/libs/" && cp "$HERE/kyty/src/kernel/memory.cpp" "$S/kyty/src/kernel/" \
        && cp "$HERE/backend/include/bc5/direct.hpp" "$HERE/backend/include/bc5/mapping_index.hpp" "$S/kyty/src/bc5/" \
        && cp "$HERE/backend/src/direct.cpp" "$S/backend/src/" && cp "$HERE/backend/include/bc5/direct.hpp" "$HERE/backend/include/bc5/mapping_index.hpp" "$S/backend/include/bc5/" \
        && cp "$BTREE/src/direct.cpp" "$S/ref/src/" && cp "$BTREE/include/bc5/direct.hpp" "$S/ref/include/bc5/" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    # 2. the backend
    distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
    rm -f "$E/backend-ref/libbc5_backend.a"; rm -rf "$E/backend-ref/obj" "$E/backend-ref/member"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/ref" "$E/backend-ref" "$BBUILD" \
        "$SA" "$E/backend-ref/libbc5_backend.a" src/direct.cpp > "$R/build-backend-ref.out" 2>&1 < /dev/null || { tail -30 "$R/build-backend-ref.out"; stop "the reference compile failed"; }
    distrobox enter ubuntu -- sh -c "cd '$E/backend-ref' && ar p '$SA' direct.cpp.o > shared-direct.o && ar p libbc5_backend.a direct.cpp.o > ref-direct.o" < /dev/null || stop "ar p"
    cmp -s "$E/backend-ref/shared-direct.o" "$E/backend-ref/ref-direct.o" || stop "the reference direct.cpp.o ($(m8 "$E/backend-ref/ref-direct.o")) is not the shared archive's ($(m8 "$E/backend-ref/shared-direct.o"))"
    echo "reference: direct.cpp.o of $P_BE_CPP compiled here == the shared archive's member ($(m8 "$E/backend-ref/ref-direct.o"))"
    rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
        "$SA" "$E/backend/libbc5_backend.a" src/direct.cpp > "$R/build-backend.out" 2>&1 < /dev/null || { tail -40 "$R/build-backend.out"; stop "the private archive failed"; }
    echo "private archive $(m8 "$E/backend/libbc5_backend.a"): errors $(grep -c 'error:' "$R/build-backend.out"), warnings $(grep -c 'warning:' "$R/build-backend.out")"
    m8 "$E/backend/libbc5_backend.a" > "$E/backend/archive.md5"
    nice -n 19 strings "$E/backend/libbc5_backend.a" > "$E/backend/strings.txt"
    grep -qx 'BC5_DIRECT_0438_A2' "$E/backend/strings.txt" || stop "the private archive has no BC5_DIRECT_0438_A2"
    grep -q 'BC5_DIRECT_0438_A2_CHECK\|tag a2c438\|tag a2): MISMATCH' "$E/backend/strings.txt" && stop "the private archive holds A2's compare-only check"
    # 3. normal and lean
    echo "MemAvailable $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB (build0438.py waits before each link while under 4 GiB)"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$E/backend/libbc5_backend.a" src/libs/bc5LleAgc.cpp src/kernel/memory.cpp > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m8 "$bin" > "$E/$v/binary.md5"
        nice -n 19 strings "$bin" > "$E/$v/strings.txt"
        nice -n 19 strings "$b/src/kyty_emulator" > "$E/$v/strings-shared.txt"
    done
    # 4. strings
    for v in normal lean; do
        want=$WORDS_NORMAL; [ $v = lean ] && want=$WORDS_LEAN
        gained=$(comm -13 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
        lost=$(comm -23 <(words "$E/$v/strings-shared.txt") <(words "$E/$v/strings.txt") | tr '\n' ' ' | sed 's/ $//')
        echo "$v $(cut -c1-8 "$E/$v/binary.md5"): words $(words "$E/$v/strings-shared.txt" | wc -l) -> $(words "$E/$v/strings.txt" | wc -l), +[$gained] -[$lost]"
        [ "$gained" = "$want" ] && [ -z "$lost" ] || stop "$v: want +[$want] -[]"
        grep -q 'BC5_DIRECT_0438_A2_CHECK\|tag a2c438\|tag a2): MISMATCH\|BC5_0438_SUBMITQ\|BC5_0438_R438_LWM' "$E/$v/strings.txt" && stop "$v holds A2_CHECK, Q438 or labelmap text"
    done
    for t in "ng438 (exp 0438): t " "wd438 (exp 0438)" "tag a1c438" "KYTY_BC5_0438_A1J" "r438o: early entries renumbered"; do
        grep -qF "$t" "$E/normal/strings.txt" || stop "normal lacks: $t"
    done
    for t in "ng438 (exp 0438)" "wd438" "tag a1c438" "KYTY_BC5_0438_A1J" "r438o: early entries renumbered" "r438 (exp 0438, b438)"; do
        grep -qF "$t" "$E/lean/strings.txt" && stop "lean holds the normal-only text: $t"
    done
    bash "$HERE/leanwords438b.sh" "$W/kytyplus-build-lean/src/kyty_emulator" "$E/lean/kyty_emulator" || stop "leanwords438b failed"
    echo "private normal $(cut -c1-8 "$E/normal/binary.md5"), lean $(cut -c1-8 "$E/lean/binary.md5"), archive $(cut -c1-8 "$E/backend/archive.md5")"
    # 5.
    [ "$(shared)" = "$before" ] || stop "the shared state changed: $(shared)"
    echo "shared after: $(shared): unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: boxbake438b.sh build" ;;
esac
