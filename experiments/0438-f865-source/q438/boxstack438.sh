#!/usr/bin/env bash
# BC5 experiment 0438 (tag stack438): the one test build of A1 + A1b + A1p + A1c (memory.cpp 286ab942, mka1 -> mka1b ->
# mka1p -> mka1c) with Q438 + A2's host change on the shared r438o unit (stack438x.cpp 8fe364d4: mka2host.py --any on
# r438o 2e6168de, then mkstack438.py, then mkq438x.py: labelmap, q438ng, BC5_0438_R438_LWM, BC5_0438_INFLIGHT_NG), linked with A2's private archive (~/bc5-work/exp0438/a2/backend/libbc5_backend.a,
# the md5 boxa2.sh wrote; backend direct.cpp 66f98937). Every arm behind its own switch: KYTY_BC5_0438_A1, _A1P, _A1J,
# BC5_DIRECT_0438_A2, _A2_CHECK, BC5_0438_SUBMITQ (and the shared EARLYREG / PLWCV). CPU only, nice 19 + ionice idle, one
# job, NO lock line. Pins the shared state (patch 0fede35d: normal 199a0f39, lean 3a20b974, archive d6638808, tree unit
# 2e6168de, memory.cpp aa7d7f5b) before and after.
#   boxstack438.sh build
# Beside this script (~/bc5-work/exp0438/stackkit): build0438.py, memory_a1x.cpp, stack438x.cpp, be/direct.hpp,
# be/mapping_index.hpp.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438/stack; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SA=$W/backend-ubuntu/libbc5_backend.a; PA=$W/exp0438/a2/backend/libbc5_backend.a
P_UNIT=2e6168de7774de436fe7e916c895180a; P_MEM=aa7d7f5b3fdbbe8d57bd440e7aa80922
P_ARCH=d6638808; P_NORMAL=199a0f39; P_LEAN=3a20b974; P_PA=$(cut -c1-8 "$W/exp0438/a2/backend/archive.md5" 2> /dev/null) # written by boxa2.sh build just before
K_MEM=286ab94268aa795a14c40ba5eb0aad9e; K_BE_CPP=66f9893767d2b18adf1a6ed3eb8aec80; K_UNIT=8fe364d4defbef516a6e58c9238165af
K_HPP=18c66de84ae1a6705462cd4953cd6633; K_MI=39952c484209fe5c64a55167f02107b7; K_PY=3fe0aacaa3a2859de7f9903e127a5a63
NICE="nice -n 19 ionice -c 3"
stop() { echo "stack438 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
build() {
    mkdir -p "$R" || stop "mkdir $R"
    local b bin rc sn sl sa v
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "the tree's unit or memory.cpp is not patch 0fede35d's"
    [ -n "$P_PA" ] && [ "$(m "$PA" | cut -c1-8)" = "$P_PA" ] || stop "A2's private archive is not $P_PA"
    grep -q "^$K_BE_CPP  ./backend/src/direct.cpp$" "$W/exp0438/a2/raw/src-md5.txt" 2> /dev/null && [ "$PA" -nt "$W/exp0438/a2/raw/src-md5.txt" ]         || stop "A2's private archive was not built from direct.cpp $K_BE_CPP (run boxa2.sh build first)"
    [ "$(m "$HERE/memory_a1x.cpp")" = "$K_MEM" ] && [ "$(m "$HERE/stack438x.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/be/direct.hpp")" = "$K_HPP" ] \
        && [ "$(m "$HERE/be/mapping_index.hpp")" = "$K_MI" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the kit is not the pinned one"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/kernel" "$S/kyty/src/bc5" || stop "mkdir $S"
    cp "$HERE/stack438x.cpp" "$S/kyty/src/libs/bc5LleAgc.cpp" && cp "$HERE/memory_a1x.cpp" "$S/kyty/src/kernel/memory.cpp" \
        && cp "$HERE/be/direct.hpp" "$S/kyty/src/bc5/direct.hpp" && cp "$HERE/be/mapping_index.hpp" "$S/kyty/src/bc5/mapping_index.hpp" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    echo "MemAvailable before the builds: $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    echo "MemAvailable $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB (build0438.py waits before each link while under 4 GiB)"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$PA" src/libs/bc5LleAgc.cpp src/kernel/memory.cpp > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"; strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); A1 $(grep -c 'KYTY_BC5_0438_A1$' "$E/$v/strings.txt"); A1P $(grep -c 'KYTY_BC5_0438_A1P' "$E/$v/strings.txt"); A1J $(grep -c 'KYTY_BC5_0438_A1J' "$E/$v/strings.txt"); A2 $(grep -c 'BC5_DIRECT_0438_A2$' "$E/$v/strings.txt"); EARLYREG $(grep -c BC5_0438_EARLYREG "$E/$v/strings.txt")"
        grep -qx 'KYTY_BC5_0438_A1' "$E/$v/strings.txt" && grep -q 'KYTY_BC5_0438_A1P' "$E/$v/strings.txt" && grep -qx 'BC5_DIRECT_0438_A2' "$E/$v/strings.txt" || stop "a switch is not in $v"
    done
    grep -q 'KYTY_BC5_0438_A1J' "$E/normal/strings.txt" || stop "normal lacks the A1J journal"
    grep -q 'KYTY_BC5_0438_A1J' "$E/lean/strings.txt" && stop "lean holds the A1J journal (BC5_LEAN not applied)"
    grep -q 'tag a1c438' "$E/normal/strings.txt" || stop "normal lacks the a1c438 counter line"
    grep -q 'tag a1c438' "$E/lean/strings.txt" && stop "lean holds the a1c438 counter line"
    grep -q 'tag a2c438' "$E/normal/strings.txt" || stop "normal lacks the a2c438 counter line"
    for v in normal lean; do for w in BC5_0438_SUBMITQ BC5_0438_EARLYREG BC5_0438_R438_LWM BC5_0438_INFLIGHT_NG; do grep -qx "$w" "$E/$v/strings.txt" || stop "$v lacks $w"; done; done
    grep -q 'r438o: early entries renumbered' "$E/normal/strings.txt" || stop "normal lacks r438o's counters"
    grep -q 'r438o: early entries renumbered' "$E/lean/strings.txt" && stop "lean holds r438o's counter line"
    echo "counter lines: normal a1c438 and a2c438 present; lean a1c438 absent (a2c438 prints only with A2_CHECK=1)"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] \
        && [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit and memory.cpp: unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: boxstack438.sh build" ;;
esac
