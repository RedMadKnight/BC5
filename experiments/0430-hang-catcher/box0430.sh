#!/usr/bin/env bash
# BC5 experiment 0430, on the box (exp 0428's box0428.sh, adapted). The top session's GO for the whole 0430 chain, 2026-11-16.
#   box0430.sh claim [what] [minutes]  takes BOX-LOCK as coordination/d19/d19box.sh does: the line appears by a hard link
#   box0430.sh build      private test build: the shared tree's unit bc5LleAgc.cpp (patch a8717e53, md5 0cda79b5) edited by
#                         mk0430.py (md5 cf1ca4d0: the dj430 catchers + F2 + G + F3; MODE=swap: mkswap0430.py, md5 42f9f976, the shared form), compiled with the shared normal build's command and
#                         relinked with the shared objects otherwise (CPU only, nice 19); writes ~/bc5-work/exp0430/kyty_emulator
#   box0430.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written. ~/src/KytyPlus and the shared build are only read. Beside this script: mk0430.py, mkswap0430.py, ho430.cpp, build0430.py.
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
    # IN_CHAIN=1 (2026-11-17 13:20, the top's order): a CPU-only build at nice 19 while this experiment's own chain run holds
    # the lock and its emulator runs; the output goes to $E/kyty_emulator only (the chain's arms use their own copies)
    if [ "${IN_CHAIN:-0}" = 1 ]; then grep -q '^exp 0430 | private run h430' "$LOCK" || stop "IN_CHAIN: the lock is not this experiment's run"
    else
    own || stop "no lock held by 0430"
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    fi
    local shared bin rc
    # the shared tree is patch a8717e53; its unit is 0cda79b5 (exp 0428's swap unit), and the shared objects are that build's
    BASE=$TREE/$U
    if [ "${MODE:-}" = f5 ] || [ "${MODE:-}" = f6 ]; then  # F5/F6 (2026-11-17): the shared unit as the 07:10 swap left it, the current shared tree and objects
        [ "$(m8 "$BASE")" = b8afba59 ] || stop "the base unit $BASE is not b8afba59"
        echo "the shared tree: diff $(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8), normal $(m8 "$B/src/kyty_emulator")"
    else
    [ "$(git -C "$TREE" diff --no-color f266548 | md5sum | cut -c1-8)" = a8717e53 ] || stop "the shared tree is not patch a8717e53"
    [ "$(m8 "$BASE")" = 0cda79b5 ] || stop "the base unit $BASE is not 0cda79b5"
    fi
    shared=$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)
    rm -rf "$S" "$E/obj"; mkdir -p "$S/src/libs" "$R"
    cp "$BASE" "$S/$U" || stop "copy $U"
    # MODE=swap (build 6 on): the shared form, mkswap0430.py's unit (the fix alone, no catcher), as the swap will ship it
    if [ "${MODE:-}" = f6 ]; then MKS=mkf6.py; EXP=dda5852f; WANTW="BC5_DIRECT_XQ_ORDER BC5_DIRECT_XQ_COUNT BC5_DIRECT_XQ_KEEP_ALL BC5_DIRECT_XQ_PRECISE"
    elif [ "${MODE:-}" = f5 ]; then MKS=mkf5.py; EXP=574301e4; WANTW="BC5_DIRECT_XQ_PRECISE BC5_DIRECT_XQ_FENCE BC5_DIRECT_XQ_ACQUIRE"
    elif [ "${MODE:-}" = swap ]; then MKS=mkswap0430.py; EXP=b8afba59; WANTW="BC5_DIRECT_ACB_RINGS BC5_DIRECT_ACB_SPLIT_LATE BC5_DIRECT_XQ_PENDING BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_FENCE"
    else MKS=mk0430.py; EXP=17a88ee8; WANTW=""; fi
    python3 -I "$HERE/$MKS" "$S" > "$R/mk.out" 2>&1 || { cat "$R/mk.out"; stop "$MKS refused"; }
    cat "$R/mk.out"
    [ "$(m8 "$S/$U")" = "$EXP" ] || stop "the edited unit is $(m8 "$S/$U"), not the laptop's $EXP"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" < /dev/null || stop "compdb failed"
    bin=$E/kyty_emulator
    [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C ${BE:+BC5_0430_ARCHIVE=$E/be-build/libbc5_backend.a BC5_0430_INCLUDE=$E/be-src/include} python3 -I "$HERE/build0430.py" "$E/compdb.json" "$S" "$E" "$B" "$bin" > "$R/build.out" 2>&1 < /dev/null
    rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$R/build.out"); warnings $(grep -c 'warning:' "$R/build.out")"
    grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build.out" | head -30
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build.out"
    if [ -n "$WANTW" ]; then set -- $WANTW; else set -- BC5_DIRECT_ACB_RINGS BC5_DIRECT_ACB_SPLIT_LATE BC5_0430_DJ BC5_0430_ARGS BC5_0430_WAVES_MS "args0430: " "halt_waves -wa none" BC5_0430_SNAP "wave helper" BC5_0430_TABLES tab0430 "ho430 F2" "ho430 F3" g0430; fi
    for w in "$@"; do
        strings "$bin" | grep -qF "$w" || stop "$w is not in the binary"
    done
    md5sum < "$bin" | cut -d' ' -f1 > "$E/binary.md5"
    echo "private binary $(cat "$E/binary.md5"), shared before $shared, after $(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)"
    [ "$shared" = "$(md5sum < "$B/src/kyty_emulator" | cut -d' ' -f1)" ] || stop "the shared binary changed"
}
# exp 0430 F4: the private backend archive: the shared archive's source (d19/export/backend, direct.cpp aeec4c09, direct.hpp
# e96e5c73) with this experiment's two files (be/direct.cpp, be/direct.hpp beside this script), the shared build's
# compiler and flags (clang++, Release, -Werror), into $E/be-build/libbc5_backend.a. Nothing shared is written.
buildbe() {
    own || stop "no lock held by 0430"
    local SRC=$W/d19/export/backend D=$E/be-src O=$E/be-build
    [ "$(m8 "$SRC/src/direct.cpp")" = aeec4c09 ] && [ "$(m8 "$SRC/include/bc5/direct.hpp")" = e96e5c73 ] || stop "the shared backend source is not aeec4c09 / e96e5c73"
    [ "$(m8 "$W/backend-ubuntu/libbc5_backend.a")" = 9aab722c ] || stop "the shared archive is not 9aab722c"
    rm -rf "$D" "$O"; cp -a "$SRC" "$D" || stop "copy the source"
    cp "$HERE/be/direct.cpp" "$D/src/direct.cpp" && cp "$HERE/be/direct.hpp" "$D/include/bc5/direct.hpp" || stop "copy the two files"
    distrobox enter ubuntu -- sh -c "cmake -S '$D' -B '$O' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DCMAKE_C_COMPILER=clang -DBC5_BUILD_TESTS=OFF -DBC5_WITH_AMDGPU=ON > '$O.cmake.log' 2>&1 && nice -n 19 ninja -C '$O' bc5_backend" > "$R/be-build.out" 2>&1 < /dev/null
    local rc=$?; echo "backend build rc $rc; errors $(grep -c 'error' "$R/be-build.out")"; grep -n "error" "$R/be-build.out" | head -20
    [ "$rc" = 0 ] && [ -s "$O/libbc5_backend.a" ] || stop "the backend build failed: $R/be-build.out"
    echo "private archive $(m8 "$O/libbc5_backend.a") (shared 9aab722c)"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-15}" ;;
    build) build ;;
    buildbe) buildbe ;;
    release) release ;;
    *) stop "usage: box0430.sh claim|build|release" ;;
esac
