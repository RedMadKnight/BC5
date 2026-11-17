#!/usr/bin/env bash
# BC5 experiment 0432, on the box. claim/release are exp 0430's box0430.sh blocks with this experiment's lines (LESSONS R35).
#   box0432.sh claim [what] [minutes]   takes BOX-LOCK by a hard link
#   box0432.sh build                    item D's private build: the shared tree's unit bc5LleAgc.cpp (patch bc39a035, md5
#                                       b8afba59) edited by mkd432.py, compiled with the shared normal build's command and
#                                       relinked with the shared objects (CPU only, nice 19): ~/bc5-work/exp0432/kyty_emulator
#   box0432.sh release                  clears the lock only if it holds this experiment's exact line
# Nothing shared is written. Beside this script: mkd432.py, build0432.py.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0432; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
U=src/libs/bc5LleAgc.cpp
m8() { md5sum < "$1" | cut -c1-8; }
stop() { echo "0432 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0432-$$.new a=$LOCK.0432-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0432 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    if [ -s "$a" ]; then mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim"; fi
    rm -f "$a" "$t"; rmdir "$c"
    [ "$(cat "$LOCK")" = "$line" ] || stop "the lock does not read back as ours"
    printf '%s\n' "$line" > "$ID"
    printf '%s\n' "exp 0432 | claimed: $1 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
    echo "claimed: $line"
}
release() {
    if own; then
        : > "$LOCK"
        printf '%s\n' "exp 0432 | released | $(date '+%F %T')" >> "$W/BOX-QUEUE"
        rm -f "$ID"
        echo "released"
    else
        stop "the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
    fi
}
build() {
    own || stop "no lock held by 0432"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local shared bin rc
    BASE=$TREE/$U
    [ "$(m8 "$BASE")" = b8afba59 ] || stop "the base unit $BASE is not b8afba59"
    shared=$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)
    [ "${shared:0:8}" = 0de9349b ] || stop "the shared normal build is ${shared:0:8}, not 0de9349b"
    rm -rf "$S" "$E/obj"; mkdir -p "$S/src/libs" "$R"
    python3 -I "$HERE/mkd432.py" "$BASE" "$S/$U" > "$R/mk.out" 2>&1 || { cat "$R/mk.out"; stop "mkd432.py refused"; }
    cat "$R/mk.out"
    [ "$(m8 "$S/$U")" = "${EXP:?the md5 of the edited unit as made on the laptop}" ] || stop "the edited unit is $(m8 "$S/$U"), not $EXP as made on the laptop"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" < /dev/null || stop "compdb failed"
    bin=$E/kyty_emulator
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0432.py" "$E/compdb.json" "$S" "$E" "$B" "$bin" > "$R/build.out" 2>&1 < /dev/null
    rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$R/build.out"); warnings $(grep -c 'warning:' "$R/build.out")"
    grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build.out" | head -30
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build.out"
    for w in BC5_DIRECT_UNMAP_NOWAIT "tag d432" BC5_DIRECT_ACB_RINGS BC5_DIRECT_XQ_FENCE; do
        strings "$bin" | grep -qF "$w" || stop "$w is not in the binary"
    done
    md5sum < "$bin" | cut -d' ' -f1 > "$E/binary.md5"
    echo "private binary $(cat "$E/binary.md5"), shared before $shared, after $(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)"
    [ "$shared" = "$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)" ] || stop "the shared binary changed"
}
case "${1:-}" in
    claim) claim "${2:-private build and runs}" "${3:-20}" ;;
    build) build ;;
    release) release ;;
    *) echo "usage: box0432.sh claim [what] [minutes] | build | release"; exit 1 ;;
esac
