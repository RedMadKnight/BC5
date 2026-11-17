#!/usr/bin/env bash
# BC5 experiment 0429, on the box, in a slot from the top session (box0425.sh's claim and release, copied, R35).
#   box0429.sh claim [what] [minutes]  takes BOX-LOCK as coordination/d19/d19box.sh does: the line appears by a hard link
#   box0429.sh build      private normal and lean builds: mk0429.py on copies of nine units of the shared tree (patch
#                         a8717e53), six of them compiled, the shared builds' objects otherwise (CPU only, nice 19);
#                         writes ~/bc5-work/exp0429/{normal,lean}/kyty_emulator and binary.md5
#   box0429.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written. ~/src/KytyPlus and the shared builds are only read. Files beside this script on the box:
# mk0429.py patch0425.py build0429.py units.sha256.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0429; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
UNITS="src/kernel/semaphore.cpp src/kernel/pthread.cpp src/loader/gamePatch.cpp src/loader/gamePatch.h src/loader/runtimeLinker.cpp src/graphics/presentation/hostMenu.cpp src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/hostInput.h src/bc5/job_arena_fix.hpp"
stop() { echo "0429 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0429-$$.new a=$LOCK.0429-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="top exp 0429 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    own || stop "no lock held by 0429"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local u v b bin rc sn sl
    sn=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); sl=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
    rm -rf "$S"; mkdir -p "$S"
    # since 2026-11-17 09:49 the shared tree carries this experiment's removal (int0429.sh): a unit it changed comes from
    # the swap's copy of it before the swap (patch 9e7c4514, the same text as at a8717e53), the others from the tree
    for u in $UNITS; do
        mkdir -p "$S/$(dirname "$u")"
        if [ -s "$E/swap/units/$(basename "$u").before-0429" ]; then cp "$E/swap/units/$(basename "$u").before-0429" "$S/$u" || stop "copy $u"
        else cp "$TREE/$u" "$S/$u" || stop "copy $u"; fi
    done
    (cd "$S" && sha256sum -c "$HERE/units.sha256") > "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the units are not the pins"; }
    python3 -I "$HERE/mk0429.py" "$S" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; stop "mk0429 failed"; }
    cat "$R/patch.out"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj"
        [ -f "$bin" ] && mv "$bin" "$bin.$(md5sum < "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        local pre=""  # exp 0429: BASE0430=1 links exp 0430's fix object (a copy, pinned) into the normal build only
        if [ "${BASE0430:-0}" = 1 ] && [ $v = normal ]; then
            pre="src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o=$E/base0430/bc5LleAgc.cpp.o"
            [ "$(md5sum < "$E/base0430/bc5LleAgc.cpp.o" | cut -d' ' -f1)" = "$(cat "$E/base0430/object.md5")" ] || stop "the exp 0430 object copy is not its pin"
        fi
        if [ "${BASE0430:-0}" = 2 ] && [ $v = normal ]; then  # exp 0430 build 7: its object AND its backend archive
            pre="src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o=$E/base0430b/bc5LleAgc.cpp.o ARCHIVE=$E/base0430b/libbc5_backend.a"
            [ "$(md5sum < "$E/base0430b/bc5LleAgc.cpp.o" | cut -d' ' -f1)" = "$(cat "$E/base0430b/object.md5")" ] && [ "$(md5sum < "$E/base0430b/libbc5_backend.a" | cut -d' ' -f1)" = "$(cat "$E/base0430b/archive.md5")" ] || stop "the exp 0430 build-7 copies are not their pins"
        fi
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0429.py" "$E/$v/compdb.json" "$S" "$E/$v" "$b" "$bin" $pre > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        md5sum < "$bin" | cut -d' ' -f1 > "$E/$v/binary.md5"
    done
    for w in KYTY_BC5_0429_PRIO_ORDER KYTY_BC5_0429_GUEST_CPUS KYTY_BC5_0429_FAST_MUTEX KYTY_BC5_0429_RR KYTY_BC5_0425_HANDOFF_US KYTY_BC5_0425_DIRECT_WAKE KYTY_BC5_0425_WAKE_SLICE_US; do
        for v in normal lean; do strings "$E/$v/kyty_emulator" | grep -qxF "$w" || stop "$w is not in $v"; done
    done
    strings "$E/normal/kyty_emulator" | grep -qxF KYTY_BC5_0429_TRACE || stop "KYTY_BC5_0429_TRACE is not in normal"
    strings "$E/normal/kyty_emulator" | grep -qxF KYTY_BC5_0429_WAITS || stop "KYTY_BC5_0429_WAITS is not in normal"
    strings "$E/lean/kyty_emulator" | grep -qF KYTY_BC5_0429_WAITS && stop "lean holds KYTY_BC5_0429_WAITS"
    if [ "${BASE0430:-0}" = 1 ] || [ "${BASE0430:-0}" = 2 ]; then  # exp 0430's switch names are not plain strings: check a symbol only its object defines
        local u0430
        local bdir=$E/base0430; [ "${BASE0430:-0}" = 2 ] && bdir=$E/base0430b
        u0430=$(comm -23 <(nm --defined-only "$bdir/bc5LleAgc.cpp.o" | awk '{print $3}' | sort -u) <(nm --defined-only "$W/kytyplus-build/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o" | awk '{print $3}' | sort -u) | grep -v '^\.L' | head -1)
        [ -n "$u0430" ] && nm "$E/normal/kyty_emulator" | grep -qF "$u0430" || stop "exp 0430's object is not in normal (BASE0430=1)"
    fi
    strings "$E/lean/kyty_emulator" | grep -qF KYTY_BC5_0429_TRACE && stop "lean holds KYTY_BC5_0429_TRACE"
    for v in normal lean; do
        for w in KYTY_BC5_JOB_ARENA_FIX "job-arena fix" "Game fixes" "Job-arena fix" bc5_job_arena_owner_help; do
            strings "$E/$v/kyty_emulator" | grep -qF "$w" && stop "$v still holds: $w"
        done
    done
    echo "private normal $(cat "$E/normal/binary.md5"), lean $(cat "$E/lean/binary.md5")"
    echo "shared normal before $sn after $(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); lean before $sl after $(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)"
    [ "$sn" = "$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1)" ] && [ "$sl" = "$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)" ] || stop "a shared binary changed"
}
base() {  # copies exp 0430's newest fix object (its next build removes obj/); pins it by md5
    local o=$W/exp0430/obj/bc5LleAgc.cpp.o
    [ -f "$o" ] || stop "no $o"
    mkdir -p "$E/base0430" && cp -p "$o" "$E/base0430/bc5LleAgc.cpp.o" && cp -p "$W/exp0430/src/src/libs/bc5LleAgc.cpp" "$E/base0430/bc5LleAgc.cpp" || stop "copy failed"
    md5sum < "$E/base0430/bc5LleAgc.cpp.o" | cut -d' ' -f1 > "$E/base0430/object.md5"
    echo "exp 0430 object $(cat "$E/base0430/object.md5"), its source $(md5sum < "$E/base0430/bc5LleAgc.cpp" | cut -c1-8)"
}
case "${1:-}" in
    base) base ;;
    claim) claim "${2:-private build}" "${3:-15}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0429.sh claim|base|build|release" ;;
esac
