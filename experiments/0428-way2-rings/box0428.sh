#!/usr/bin/env bash
# BC5 experiment 0428, on the box (exp 0425's box0425.sh, adapted). The top session's GO for the whole way-2 chain, 2026-11-16.
#   box0428.sh claim [what] [minutes]  takes BOX-LOCK as coordination/d19/d19box.sh does: the line appears by a hard link
#   box0428.sh build      private test build: the unit bc5LleAgc.cpp of the shared tree (patch 700fd4c2, md5 3e847e03)
#                         edited by mk0428.py (md5 3481b83e), compiled with the shared normal build's command and relinked
#                         with the shared objects otherwise (CPU only, nice 19); writes ~/bc5-work/exp0428/kyty_emulator
#                         and binary.md5
#   box0428.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written. ~/src/KytyPlus and the shared build are only read. Beside this script on the box: mk0428.py,
# ed0419g.py, build0428.py.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0428; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
U=src/libs/bc5LleAgc.cpp
m8() { md5sum < "$1" | cut -c1-8; }
stop() { echo "0428 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0428-$$.new a=$LOCK.0428-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="exp 0428 | token $(date +%s)$$ | $1, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    printf '%s\n' "exp 0428 | claimed: $1 | $(date '+%F %T')" >> "$W/BOX-QUEUE"
    echo "claimed: $line"
}
release() {
    if own; then
        : > "$LOCK"
        printf '%s\n' "exp 0428 | released | $(date '+%F %T')" >> "$W/BOX-QUEUE"
        rm -f "$ID"
        echo "released"
    else
        stop "the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
    fi
}
build() {
    own || stop "no lock held by 0428"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    local shared bin rc
    # iteration 3 (after the 14:37 swap): the shared tree is patch 2c82a979; the base unit is the swap's saved copy of
    # 700fd4c2's unit (3e847e03), and the shared objects are the swapped build's (its four title rows for way 2 included)
    [ "$(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8)" = 2c82a979 ] || stop "the shared tree is not patch 2c82a979"
    BASE=$E/swap/bc5LleAgc.cpp.before-0428
    [ "$(m8 "$BASE")" = 3e847e03 ] || stop "the base unit $BASE is not 3e847e03"
    shared=$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)
    rm -rf "$S" "$E/obj"; mkdir -p "$S/src/libs" "$R"
    cp "$BASE" "$S/$U" || stop "copy $U"
    python3 -I "$HERE/mk0428.py" "$S" > "$R/mk.out" 2>&1 || { cat "$R/mk.out"; stop "mk0428.py refused"; }
    cat "$R/mk.out"
    [ "$(m8 "$S/$U")" = 3481b83e ] || stop "the edited unit is $(m8 "$S/$U"), not the laptop's 3481b83e"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" < /dev/null || stop "compdb failed"
    bin=$E/kyty_emulator
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0428.py" "$E/compdb.json" "$S" "$E" "$B" "$bin" > "$R/build.out" 2>&1 < /dev/null
    rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$R/build.out"); warnings $(grep -c 'warning:' "$R/build.out")"
    grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build.out" | head -30
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build.out"
    for w in BC5_DIRECT_ACB_RINGS BC5_DIRECT_ACB_QUEUE_STATE BC5_DIRECT_ACB_MEC_INDIRECT BC5_DIRECT_ACB_STATE_NO_WALK BC5_DIRECT_ACB_SPLIT_LATE "tag w428c" "tag w428)" "tag aq424)"; do
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
    *) stop "usage: box0428.sh claim|build|release" ;;
esac
