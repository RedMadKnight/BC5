#!/usr/bin/env bash
# BC5 experiment 0433, on the box, in a slot from the top session (box0429.sh's claim and release, copied, R35).
#   box0433.sh claim [what] [minutes]  takes BOX-LOCK as box0429.sh does (the line appears by a hard link)
#   box0433.sh build      private normal and lean builds of ports pack 1 (patch 0002 on the shared tree), CPU only, nice 19:
#                         copies of the 17 units the pack changes (pinned in units.sha256, with bc5LleAgc.cpp at exp 0430's
#                         d1388db0: the pack is tested on top of 0430's swap), 0002 applied to the copies, compiled with the
#                         shared builds' own commands and linked with their other objects (build0433.py); a private backend
#                         archive: a copy of the shared one whose policy.cpp member is rebuilt with the 0x51 count
#                         (policy0433.diff on the shared source, pinned in backend.sha256).
#                         Writes ~/bc5-work/exp0433/{normal,lean}/kyty_emulator, binary.md5, backend/libbc5_backend.a
#   box0433.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written; ~/src/KytyPlus, ~/src/bc5 and the shared builds are only read. ALLOW_EF2=1 accepts the tree
# at patch ef2ff54f (bc5LleAgc.cpp before 0430's swap) instead of d1388db0. Files beside this script on the box:
# build0433.py units.sha256 backend.sha256 policy0433.diff 0002-bc5-ports-pack1.patch.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0433; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; BTREE=$HOME/src/bc5/backend; BBUILD=$W/backend-ubuntu; HERE=$(cd "$(dirname "$0")" && pwd)
UNITS="src/common/hostException.cpp src/common/platform/sysLinuxFileIO.cpp src/common/platform/sysLinuxVirtual.cpp src/common/threads.cpp src/kernel/eventQueue.cpp src/kernel/memory.cpp src/kernel/pthread.cpp src/kernel/semaphore.cpp src/libs/ajm.cpp src/libs/controller.cpp src/libs/libAmpr.cpp src/libs/libAppContent.cpp src/libs/libSaveData.cpp src/libs/libSysmodule.cpp src/libs/libUserService.cpp src/libs/network.cpp"
WORDS="KYTY_BC5_P1_EQ_WAKE_ALL KYTY_BC5_P1_NO_COND_REGISTRY KYTY_BC5_P1_FAULT_MASK KYTY_BC5_P1_SEMA_UAF KYTY_BC5_P1_AMPR_RESULT KYTY_BC5_P1_APR_FILE_ID KYTY_BC5_P1_COND_SIGNAL_ONE KYTY_BC5_P1_ALTSTACK KYTY_BC5_P1_PTHREAD_KEYS KYTY_BC5_P1_PROT_RANGES KYTY_BC5_P1_FILE_UNBUFFERED KYTY_BC5_P1_AJM_GAPLESS KYTY_BC5_P1_AMPR_FILTER KYTY_BC5_P1_FATAL_TO_ERROR"
stop() { echo "0433 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0433-$$.new a=$LOCK.0433-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="top exp 0433 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
    mkdir "$c" 2> /dev/null || stop "another claim runs, or $c was left behind"
    fail() { rm -f "$t"; rmdir "$c"; stop "$1"; }
    printf '%s\n' "$line" > "$t" || fail "cannot write $t"
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        { [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; } && fail "$LOCK is not a plain file"
        [ -s "$LOCK" ] && fail "foreign lock: $(cat "$LOCK")"
        mv -T "$LOCK" "$a" || fail "the lock moved under us"
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        [ -s "$a" ] || rm -f "$a"
        fail "lost the claim to: $(cat "$LOCK" 2> /dev/null)"
    fi
    if [ -s "$a" ]; then
        local w; w=$(cat "$a"); mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim: $w"
    fi
    rm -f "$a" "$t"; rmdir "$c" || stop "cannot remove $c"
    printf '%s\n' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"
    own || stop "the lock does not read back as ours"
    echo "claimed: $line"
}
release() {
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; stop "the lock could not be released"; fi
    stop "the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
}
build() {
    own || stop "no lock held by 0433"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local u v b bin rc sn sl sa pins
    sn=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); sl=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
    sa=$(md5sum < "$BBUILD/libbc5_backend.a" | cut -d' ' -f1)
    rm -rf "$S"; mkdir -p "$S/kyty" "$S/backend/src" "$E/backend"
    # the shared tree: the 17 units as pinned, and bc5LleAgc.cpp at d1388db0 (exp 0430's swap) unless ALLOW_EF2=1
    pins=$R/units.pins; grep -v bc5LleAgc "$HERE/units.sha256" > "$pins"
    [ "${ALLOW_EF2:-0}" = 1 ] || grep bc5LleAgc "$HERE/units.sha256" >> "$pins"
    (cd "$TREE" && sha256sum -c "$pins") > "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the shared tree is not the pinned one (0430's swap not in? ALLOW_EF2=1 takes ef2ff54f)"; }
    for u in $UNITS src/common/hostException.h; do
        mkdir -p "$S/kyty/$(dirname "$u")"; cp "$TREE/$u" "$S/kyty/$u" || stop "copy $u"
    done
    (cd "$S/kyty" && git apply "$HERE/0002-bc5-ports-pack1.patch") > "$R/apply.out" 2>&1 || { cat "$R/apply.out"; stop "0002 does not apply to the copies"; }
    [ -s "$S/kyty/src/bc5/ports_pack1.hpp" ] || stop "0002 made no ports_pack1.hpp"
    # backend: policy.cpp from the shared source, pinned, with the count
    (cd "$HOME/src/bc5" && sha256sum -c "$HERE/backend.sha256") > "$R/backend-pin.txt" 2>&1 || { cat "$R/backend-pin.txt"; stop "the shared backend's policy.cpp is not the pinned one"; }
    cp "$BTREE/src/policy.cpp" "$S/backend/src/policy.cpp" || stop "copy policy.cpp"
    (cd "$S" && git apply -p1 "$HERE/policy0433.diff") > "$R/policy-apply.out" 2>&1 \
        || { cat "$R/policy-apply.out"; stop "policy0433.diff does not apply"; }
    distrobox enter ubuntu -- sh -c "cd '$BBUILD' && ninja -t compdb" > "$E/backend/compdb.json" 2> "$R/compdb-backend.err" < /dev/null || stop "backend compdb failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0433.py" archive "$E/backend/compdb.json" "$S/backend" "$E/backend" "$BBUILD" \
        "$BBUILD/libbc5_backend.a" "$E/backend/libbc5_backend.a" src/policy.cpp > "$R/build-backend.out" 2>&1 < /dev/null \
        || { tail -30 "$R/build-backend.out"; stop "backend archive failed"; }
    md5sum < "$E/backend/libbc5_backend.a" | cut -d' ' -f1 > "$E/backend/archive.md5"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(md5sum < "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0433.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            "ARCHIVE=$E/backend/libbc5_backend.a" $UNITS > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        md5sum < "$bin" | cut -d' ' -f1 > "$E/$v/binary.md5"
    done
    for v in normal lean; do
        for w in $WORDS; do strings "$E/$v/kyty_emulator" | grep -qxF "$w" || stop "$w is not in $v"; done
        strings "$E/$v/kyty_emulator" | grep -qF "CONTEXT_REG_RMW (0x51)" || stop "the 0x51 count is not in $v"
    done
    echo "private normal $(cat "$E/normal/binary.md5"), lean $(cat "$E/lean/binary.md5"), backend archive $(cat "$E/backend/archive.md5")"
    [ "$sn" = "$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1)" ] && [ "$sl" = "$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)" ] \
        && [ "$sa" = "$(md5sum < "$BBUILD/libbc5_backend.a" | cut -d' ' -f1)" ] || stop "a shared binary or the shared archive changed"
    echo "shared normal $sn, lean $sl, archive $sa: unchanged"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-20}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0433.sh claim|build|release" ;;
esac
