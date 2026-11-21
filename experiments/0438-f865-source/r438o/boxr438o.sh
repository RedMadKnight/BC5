#!/usr/bin/env bash
# BC5 experiment 0438 (tag r438o): the private build of r438o (F874, F875: r438's early writes keep their ring order in
# g_plw and survive its trim) for the lean A/B on ASTRO BOT and the normal counter run. The host unit only: r438o.cpp
# (2e6168de, mkr438o.py on the bake unit ff9e8fe2) as src/libs/bc5LleAgc.cpp, each build with the shared build's own
# commands (build0438.py emu) and the shared archive d6638808. CPU only, nice 19 + ionice idle, one job, NO lock line
# (the top session's approval of 2026-11-21). Pins the shared state before and after.
#   boxr438o.sh build
# Beside this script (~/bc5-work/exp0438/r438okit): build0438.py, r438o.cpp.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0438/r438o; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SA=$W/backend-ubuntu/libbc5_backend.a
P_UNIT=ff9e8fe2e4139264ebaf74f9e84bd892; P_MEM=aa7d7f5b3fdbbe8d57bd440e7aa80922
P_ARCH=d6638808; P_NORMAL=b1b57df9; P_LEAN=d3485ed4
K_UNIT=2e6168de7774de436fe7e916c895180a; K_PY=3fe0aacaa3a2859de7f9903e127a5a63
NICE="nice -n 19 ionice -c 3"
stop() { echo "r438o STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
words() { strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
build() {
    mkdir -p "$R" || stop "mkdir $R"
    local b bin rc sn sl sa v
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "the tree's unit or memory.cpp is not patch 9889b06a's"
    [ "$(m "$HERE/r438o.cpp")" = "$K_UNIT" ] && [ "$(m "$HERE/build0438.py")" = "$K_PY" ] || stop "the kit is not the pinned one"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" || stop "mkdir $S"
    cp "$HERE/r438o.cpp" "$S/kyty/src/libs/bc5LleAgc.cpp" || stop "copy the kit"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    echo "MemAvailable $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB (build0438.py waits before each link while under 4 GiB)"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            src/libs/bc5LleAgc.cpp > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|LINK NOT" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"; strings "$bin" > "$E/$v/strings.txt"
    done
    for v in normal lean; do
        local shared=$W/kytyplus-build$([ $v = lean ] && echo -lean)/src/kyty_emulator
        if [ "$(words "$shared")" = "$(words "$E/$v/kyty_emulator")" ]; then echo "$v: switch words equal to the shared $v build's ($(words "$shared" | wc -l))"
        else echo "$v: switch words differ from the shared build:"; diff <(words "$shared") <(words "$E/$v/kyty_emulator"); stop "switch words changed in $v"; fi
        grep -qx BC5_0438_EARLYREG "$E/$v/strings.txt" && grep -qx BC5_0438_PLWCV "$E/$v/strings.txt" || stop "$v lacks EARLYREG or PLWCV"
    done
    grep -q 'r438o: early entries renumbered' "$E/normal/strings.txt" || stop "normal lacks the r438o counters"
    grep -q 'r438o: early entries renumbered' "$E/lean/strings.txt" && stop "lean holds the r438o counter line"
    grep -q 'r438 (exp 0438, b438): t ' "$E/lean/strings.txt" && stop "lean holds r438's count line"
    echo "r438o: normal $(cut -c1-8 "$E/normal/binary.md5") (counter line present), lean $(cut -c1-8 "$E/lean/binary.md5") (counter and count lines absent)"
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] \
        && [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/kernel/memory.cpp")" = "$P_MEM" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree unit and memory.cpp: unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: boxr438o.sh build" ;;
esac
