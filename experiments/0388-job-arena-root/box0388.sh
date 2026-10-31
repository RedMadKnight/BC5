#!/usr/bin/env bash
# BC5 experiment 0388, on the box, in a slot from the top session.
#   box0388.sh claim      takes BOX-LOCK as coordination/d19/d19box.sh does: the line appears by a hard link
#   box0388.sh build      private test build: four patched units, the shared objects otherwise (CPU only, nice 19, ~5 min)
#   box0388.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written. ~/src/KytyPlus and the shared build are only read.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0388; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
UNITS="src/kernel/pthread.cpp src/kernel/pthread.h src/kernel/semaphore.cpp src/libs/libKernel.cpp"
stop() { echo "0388 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0388-$$.new a=$LOCK.0388-$$.aside line
    pgrep -x kyty_emulator > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="top exp 0388 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    own || stop "no lock held by 0388"
    pgrep -x kyty_emulator > /dev/null && stop "an emulator runs"
    local u shared bin rc
    (cd "$TREE" && sha256sum -c "$HERE/units.sha256") > "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the shared tree's units are not the pins"; }
    shared=$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)
    rm -rf "$S" "$E/obj"; mkdir -p "$S/src/bc5"
    for u in $UNITS; do mkdir -p "$S/$(dirname "$u")"; cp "$TREE/$u" "$S/$u" || stop "copy $u"; done
    cp "$HERE/cpu_model.hpp" "$S/src/bc5/" || stop "no cpu_model.hpp"
    python3 -I "$HERE/patch0388.py" "$S" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; stop "patch failed"; }
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || stop "compdb failed"
    bin=$E/kyty_emulator
    [ -f "$bin" ] && mv "$bin" "$bin.$(md5sum < "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0388.py" "$E/compdb.json" "$S" "$E" "$B" "$bin" > "$R/build.out" 2>&1
    rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$R/build.out")"
    grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build.out"
    [ "$(strings "$bin" | grep -c 'KYTY_BC5_0388_')" -ge 5 ] || stop "the switches are not in the binary"
    echo "private binary $(md5sum < "$bin" | cut -d' ' -f1), shared before $shared, after $(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)"
    [ "$shared" = "$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)" ] || stop "the shared binary changed"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-15}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0388.sh claim|build|release" ;;
esac
