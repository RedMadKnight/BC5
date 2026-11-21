#!/usr/bin/env bash
# BC5 experiment 0439 (tag dc439): the private build of the DCC present (dcc-present-design.md): bc5LleAgc.cpp and
# videoOut.cpp from mk439.py over the shared tree's units (patch 589ef163 since 2026-11-21 21:08, exp 0438's bake; 0fede35d before), with src/bc5/dc0439.hpp, each compiled with
# the shared build's own command and linked with the shared backend archive (build0438.py emu). Normal and lean. CPU only,
# nice 19 + ionice idle. Pins the shared state before and after; writes nothing shared.
#   box439.sh build
# Beside this script (~/bc5-work/exp0439/k439): build0438.py, new/bc5LleAgc.cpp, new/videoOut.cpp, new/dc0439.hpp,
# new/eventQueue.cpp, new/ib_chain.hpp and new/be/{direct,policy,full_state}.cpp.
# exp 0439 (tag ib439, BC5_DIRECT_IB_CHAIN): a private backend archive too: the shared archive with direct.cpp.o,
# policy.cpp.o and full_state.cpp.o compiled from new/be/ (build0438.py archive, the backend's own compile commands, the
# copy's include first); the shared backend source must be main's (pinned below). The emulators link that archive.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0439/k439; R=$E/raw; S=$E/src; HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SA=$W/backend-ubuntu/libbc5_backend.a; BBUILD=$W/backend-ubuntu; BTREE=$W/d19/export/backend
P_BE_DIRECT=1b8b55ec; P_BE_POLICY=107bb1b6; P_BE_FULL=29f7dd6d
P_UNIT=ed489aca99adacbdd449cf460417dc4c; P_VO=6785425ea472815fc85713cec6cc5630
P_ARCH=a548a249; P_NORMAL=30546370; P_LEAN=05fd749d
NICE="nice -n 19 ionice -c 3"
stop() { echo "dc439 build STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
build() {
    mkdir -p "$R" || stop "mkdir $R"
    local b bin rc sn sl sa v
    sn=$(m "$W/kytyplus-build/src/kyty_emulator"); sl=$(m "$W/kytyplus-build-lean/src/kyty_emulator"); sa=$(m "$SA")
    [ "${sn:0:8}" = "$P_NORMAL" ] && [ "${sl:0:8}" = "$P_LEAN" ] && [ "${sa:0:8}" = "$P_ARCH" ] || stop "the shared builds are not $P_NORMAL/$P_LEAN/$P_ARCH"
    [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/graphics/presentation/videoOut.cpp")" = "$P_VO" ] || stop "the tree's units are not patch 589ef163's"
    [ "$(m "$BTREE/src/direct.cpp" | cut -c1-8)" = $P_BE_DIRECT ] && [ "$(m "$BTREE/src/policy.cpp" | cut -c1-8)" = $P_BE_POLICY ]         && [ "$(m "$BTREE/src/full_state.cpp" | cut -c1-8)" = $P_BE_FULL ] || stop "the shared backend source is not main's"
    rm -rf "$S"; mkdir -p "$S/kyty/src/libs" "$S/kyty/src/graphics/presentation" "$S/kyty/src/bc5" "$S/kyty/src/kernel"         "$S/backend/src" "$S/backend/include/bc5" "$E/backend" || stop "mkdir $S"
    cp "$HERE/new/bc5LleAgc.cpp" "$S/kyty/src/libs/bc5LleAgc.cpp" && cp "$HERE/new/videoOut.cpp" "$S/kyty/src/graphics/presentation/videoOut.cpp" \
        && cp "$HERE/new/dc0439.hpp" "$S/kyty/src/bc5/dc0439.hpp" && cp "$HERE/new/eventQueue.cpp" "$S/kyty/src/kernel/eventQueue.cpp"         && cp "$HERE/new/ib_chain.hpp" "$S/kyty/src/bc5/ib_chain.hpp" && cp "$HERE/new/ib_chain.hpp" "$S/backend/include/bc5/ib_chain.hpp"         && cp "$HERE/new/sv0439.hpp" "$S/kyty/src/bc5/sv0439.hpp" && cp "$HERE/new/be/direct.cpp" "$HERE/new/be/policy.cpp" "$HERE/new/be/full_state.cpp" "$S/backend/src/" || stop "copy the units"
    NP=""; if [ -f "$HERE/new/libNp.cpp" ]; then cp "$HERE/new/libNp.cpp" "$S/kyty/src/libs/libNp.cpp" || stop "copy libNp.cpp"; NP=src/libs/libNp.cpp; fi # exp 0439 (tag sv439)
    # exp 0439 (tags st439, th439, rc439, mkk439.py): semaphore.cpp, pthread.cpp and libKernel.cpp when generated copies are there
    for u in kernel/semaphore.cpp kernel/pthread.cpp libs/libKernel.cpp; do
        b=$(basename "$u")
        if [ -f "$HERE/new/$b" ]; then cp "$HERE/new/$b" "$S/kyty/src/$u" || stop "copy $b"; NP="$NP src/$u"; fi
    done
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    echo "MemAvailable before the builds: $(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
    [ "$(awk '/^MemAvailable/{print $2}' /proc/meminfo)" -gt 3000000 ] || stop "under 3 GiB available: not building now"
    distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
    rm -f "$E/backend/libbc5_backend.a"; rm -rf "$E/backend/obj" "$E/backend/member"
    distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD"         "$SA" "$E/backend/libbc5_backend.a" src/direct.cpp src/policy.cpp src/full_state.cpp > "$R/build-backend.out" 2>&1 < /dev/null         || { tail -40 "$R/build-backend.out"; stop "backend archive failed"; }
    echo "backend: errors $(grep -c 'error:' "$R/build-backend.out"); warnings $(grep -c 'warning:' "$R/build-backend.out"); archive $(m "$E/backend/libbc5_backend.a" | cut -c1-8)"
    grep -n "warning:" "$R/build-backend.out" | head -5
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(m "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- $NICE env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0438.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$E/backend/libbc5_backend.a" src/libs/bc5LleAgc.cpp src/graphics/presentation/videoOut.cpp src/kernel/eventQueue.cpp $NP > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        m "$bin" > "$E/$v/binary.md5"; strings "$bin" > "$E/$v/strings.txt"
        echo "$v: $(cut -c1-8 "$E/$v/binary.md5"); BC5_DIRECT_DCC_PRESENT $(grep -c 'BC5_DIRECT_DCC_PRESENT' "$E/$v/strings.txt"); dc439 lines $(grep -c 'tag dc439' "$E/$v/strings.txt")"
        grep -q BC5_DIRECT_DCC_PRESENT "$E/$v/strings.txt" && grep -q BC5_DIRECT_EAGER_GPU_WRITE "$E/$v/strings.txt" && grep -q BC5_DIRECT_IB_CHAIN "$E/$v/strings.txt" || stop "a switch is not in $v"
        echo "$v: tag ib439 lines $(grep -c 'tag ib439' "$E/$v/strings.txt")"
    done
    [ "$sn" = "$(m "$W/kytyplus-build/src/kyty_emulator")" ] && [ "$sl" = "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" ] && [ "$sa" = "$(m "$SA")" ] \
        && [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$P_UNIT" ] && [ "$(m "$TREE/src/graphics/presentation/videoOut.cpp")" = "$P_VO" ] || stop "a shared file changed"
    echo "shared normal ${sn:0:8}, lean ${sl:0:8}, archive ${sa:0:8}, tree units: unchanged"
}
case "${1:-}" in
    build) build ;;
    *) stop "usage: box439.sh build" ;;
esac
