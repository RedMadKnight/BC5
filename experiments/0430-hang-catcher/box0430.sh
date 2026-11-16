#!/usr/bin/env bash
# BC5 experiment 0430, on the box (exp 0428's box0428.sh, adapted). The top session's GO for the whole 0430 chain, 2026-11-16.
#   box0430.sh claim [what] [minutes]  takes BOX-LOCK as coordination/d19/d19box.sh does: the line appears by a hard link
#   box0430.sh build      private test build: the shared tree's unit bc5LleAgc.cpp (patch a8717e53, md5 0cda79b5) edited by
#                         mk0430.py (md5 51f7e7b5 since build 2: the dj430 catchers), compiled with the shared normal build's command and
#                         relinked with the shared objects otherwise (CPU only, nice 19); writes ~/bc5-work/exp0430/kyty_emulator
#   box0430.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written. ~/src/KytyPlus and the shared build are only read. Beside this script: mk0430.py, build0430.py.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0430; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
U=src/libs/bc5LleAgc.cpp
m8() { md5sum < "$1" | cut -c1-8; }
stop() { echo "0430 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0430-$$.new a=$LOCK.0430-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0430 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    printf '%s\n' "exp 0430 | claimed: $1 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
    echo "claimed: $line"
}
release() {
    if own; then
        : > "$LOCK"
        printf '%s\n' "exp 0430 | released | $(date '+%F %T')" >> "$W/BOX-QUEUE"
        rm -f "$ID"
        echo "released"
    else
        stop "the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
    fi
}
build() {
    own || stop "no lock held by 0430"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local shared bin rc
    # the shared tree is patch a8717e53; its unit is 0cda79b5 (exp 0428's swap unit), and the shared objects are that build's
    [ "$(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8)" = a8717e53 ] || stop "the shared tree is not patch a8717e53"
    BASE=$TREE/$U
    [ "$(m8 "$BASE")" = 0cda79b5 ] || stop "the base unit $BASE is not 0cda79b5"
    shared=$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)
    rm -rf "$S" "$E/obj"; mkdir -p "$S/src/libs" "$R"
    cp "$BASE" "$S/$U" || stop "copy $U"
    python3 -I "$HERE/mk0430.py" "$S" > "$R/mk.out" 2>&1 || { cat "$R/mk.out"; stop "mk0430.py refused"; }
    cat "$R/mk.out"
    [ "$(m8 "$S/$U")" = 51f7e7b5 ] || stop "the edited unit is $(m8 "$S/$U"), not the laptop's 51f7e7b5"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" < /dev/null || stop "compdb failed"
    bin=$E/kyty_emulator
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0430.py" "$E/compdb.json" "$S" "$E" "$B" "$bin" > "$R/build.out" 2>&1 < /dev/null
    rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$R/build.out"); warnings $(grep -c 'warning:' "$R/build.out")"
    grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build.out" | head -30
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build.out"
    for w in BC5_DIRECT_ACB_RINGS BC5_DIRECT_ACB_SPLIT_LATE BC5_0430_DJ BC5_0430_ARGS BC5_0430_WAVES_MS "args0430: " "halt_waves -wa none" BC5_0430_SNAP "wave helper"; do
        strings "$bin" | grep -qF "$w" || stop "$w is not in the binary"
    done
    md5sum < "$bin" | cut -d' ' -f1 > "$E/binary.md5"
    echo "private binary $(cat "$E/binary.md5"), shared before $shared, after $(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)"
    [ "$shared" = "$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)" ] || stop "the shared binary changed"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-15}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0430.sh claim|build|release" ;;
esac
