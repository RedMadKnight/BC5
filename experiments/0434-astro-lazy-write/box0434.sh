#!/bin/bash
# BC5 experiment 0434: the private test build of ud434 (BC5_DIRECT_UD_TARGETS) on the BC-250.
#   box0434.sh build      the shared tree's src/libs/bc5LleAgc.cpp must have md5 8eb42a10 (patch 59f00d27); the patched copy
#                         ~/bc5-work/exp0434/src/src/libs/bc5LleAgc.cpp (md5 given as $2) is compiled with the shared normal and
#                         the shared lean build's own commands and relinked with their objects otherwise (CPU only, nice 19):
#                         ~/bc5-work/exp0434/normal/kyty_emulator and ~/bc5-work/exp0434/lean/kyty_emulator
#   box0434.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written: ~/src/KytyPlus and the shared builds are only read. Beside this script: build0434.py.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0434; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
HERE=$(cd "$(dirname "$0")" && pwd)
m8() { md5sum "$1" | cut -c1-8; }
stop() { echo "STOP: $*"; release; exit 3; }
release() {
    [ -f "$ID" ] || return 0
    local line; line=$(cat "$ID")
    if [ -f "$LOCK" ] && grep -qxF "$line" "$LOCK"; then
        grep -vxF "$line" "$LOCK" > "$LOCK.tmp.$$"; cat "$LOCK.tmp.$$" > "$LOCK"; rm -f "$LOCK.tmp.$$"
        echo "lock released: $line"
    fi
    rm -f "$ID"
}
guard() {
    # LESSONS R38: match the process name exactly, never a command line (an ssh shell holding the word matched itself).
    if ps -eo comm= | grep -qx kyty_emulator; then
        [ -f "$ID" ] && grep -qxF "$(cat "$ID")" "$LOCK" 2>/dev/null || { echo "an emulator runs without our lock: stop"; exit 3; }
    fi
    if [ -s "$LOCK" ] && ! { [ -f "$ID" ] && grep -qxF "$(cat "$ID")" "$LOCK"; }; then
        echo "BOX-LOCK holds another line:"; cat "$LOCK"; exit 3
    fi
}
case "${1:-}" in
build)
    want=${2:?md5 of the patched bc5LleAgc.cpp}
    mkdir -p "$R"
    guard
    line="exp0434 private build of ud434 (CPU only, nice 19) | $(date '+%F %T') | ~15 min"
    echo "$line" > "$ID"; echo "$line" >> "$LOCK"
    T=$HOME/src/KytyPlus
    [ "$(m8 "$T/src/libs/bc5LleAgc.cpp")" = 8eb42a10 ] || stop "the shared tree's bc5LleAgc.cpp is $(m8 "$T/src/libs/bc5LleAgc.cpp"), not 8eb42a10"
    [ "$(md5sum "$S/src/libs/bc5LleAgc.cpp" | cut -d' ' -f1)" = "$want" ] || stop "the patched copy is not $want"
    for v in normal lean; do
        B=$W/kytyplus-build; [ "$v" = lean ] && B=$W/kytyplus-build-lean
        OUT=$E/$v; mkdir -p "$OUT"
        echo "== $v: shared binary $(m8 "$B/src/kyty_emulator") in $B"
        distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$OUT/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb failed ($v)"
        bin=$OUT/kyty_emulator
        [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0434.py" "$OUT/compdb.json" "$S" "$OUT" "$B" "$bin" > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -30
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-$v.out"
        echo "$v: $bin $(m8 "$bin"); ud434 strings: $(grep -c 'tag ud434' <(strings "$bin")); BC5_DIRECT_UD_TARGETS: $(grep -c 'BC5_DIRECT_UD_TARGETS' <(strings "$bin"))"
    done
    release
    ;;
release) release ;;
*) echo "usage: $0 build <md5> | release"; exit 2 ;;
esac
