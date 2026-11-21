#!/usr/bin/env bash
# BC5 experiment 0438 (tags a1, a1b, a1p, a2): the full-tree compile of A1 + A1b + A1p (memory.cpp 09d560f1 by
# mka1 -> mka1b -> mka1p) with A2 (the host unit a2host.cpp 0402a183 and the A2 headers), linked with A2's private
# archive (~/bc5-work/exp0438/a2/backend/libbc5_backend.a, b419da49). CPU only, nice 19 + ionice idle, NO lock line
# (the top session's GO of 2026-11-21; exp 0439 holds BOX-LOCK). Normal and lean, each with the shared build's own
# commands (build0438.py emu). Pins the shared state before and after.
#   boxa1.sh build
# Beside this script (~/bc5-work/exp0438/a1kit): build0438.py, memory_a1x.cpp, a2host.cpp, be/direct.hpp,
# be/mapping_index.hpp.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438/a1; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SA=$W/backend-ubuntu/libbc5_backend.a; PA=$W/exp0438/a2/backend/libbc5_backend.a
P_UNIT=ff9e8fe2e4139264ebaf74f9e84bd892; P_MEM=aa7d7f5b3fdbbe8d57bd440e7aa80922
P_ARCH=d6638808; P_NORMAL=b1b57df9; P_LEAN=d3485ed4; P_PA=b419da49
K_MEM=09d560f1f5625d022bab5da20fcd9099; K_UNIT=0402a183e527bca6d1d27b5d02bc0c38
K_HPP=18c66de84ae1a6705462cd4953cd6633; K_MI=39952c484209fe5c64a55167f02107b7; K_PY=5dfb35d884bee8af31d81e3ad8b92548
NICE="nice -n 19 ionice -c 3"
stop() { echo "a1 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
build() {
    mkdir -p "$R" || stop "mkdir $R"
    local b bin rc sn sl sa v
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "the tree's unit or memory.cpp is not patch 9889b06a's"
    [ "$(m "$PA" | cut -c1-8)" = "$P_PA" ] || stop "A2's private archive is not $P_PA"
    [ "$(m "$HERE/memory_a1x.cpp")" = "$K_MEM" ] && [ "$(m "$HERE/a2host.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/be/direct.hpp")" = "$K_HPP" ] \
        && [ "$(m "$HERE/be/mapping_index.hpp")" = "$K_MI" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the kit is not the pinned one"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/kernel" "$S/kyty/src/bc5" || stop "mkdir $S"
    cp "$HERE/a2host.cpp" "$S/kyty/src/libs/bc5LleAgc.cpp" && cp "$HERE/memory_a1x.cpp" "$S/kyty/src/kernel/memory.cpp" \
        && cp "$HERE/be/direct.hpp" "$S/kyty/src/bc5/direct.hpp" && cp "$HERE/be/mapping_index.hpp" "$S/kyty/src/bc5/mapping_index.hpp" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    echo "MemAvailable before the builds: $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    [ "$(awk '/^MemAvailable/{print $2}' /proc/meminfo)" -gt 3000000 ] || stop "under 3 GiB available: not building now"
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
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] \
        && [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit and memory.cpp: unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: boxa1.sh build" ;;
esac
