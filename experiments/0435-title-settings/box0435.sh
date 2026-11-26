#!/usr/bin/env bash
# BC5 experiment 0435, on the box, in a slot from the top session (box0433.sh's claim and release, copied, R35).
#   box0435.sh claim [what] [minutes]  takes BOX-LOCK as box0433.sh does (the line appears by a hard link)
#   box0435.sh build      private normal and lean builds with each title's own settings and window mode, CPU only, nice 19:
#                         copies of the 5 tree files exp 0435 edits (pinned in units.sha256, patch 59f00d27) and main.cpp,
#                         apply0435.py on the copies (+ src/bc5/title_settings.hpp), the 3 units that change
#                         (hostInput.cpp, window.cpp, main.cpp) compiled with the shared builds' own commands and linked
#                         with their other objects and the shared backend archive (build0435.py = build0433.py).
#                         Writes ~/bc5-work/exp0435/{normal,lean}/kyty_emulator and binary.md5
#   box0435.sh release    clears the lock only if it holds this experiment's exact line
# Nothing shared is written; ~/src/KytyPlus and the shared builds are only read. Files beside this script on the box:
# build0435.py apply0435.py title_settings.hpp units.sha256.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0435; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
TREE=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
FILES="src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/hostInput.h src/graphics/presentation/window.h src/graphics/presentation/window/window.cpp src/bc5/switch_defaults.hpp src/main.cpp"
UNITS="src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/window.cpp src/main.cpp"
stop() { echo "0435 STOP: $*"; exit 1; }
running() { ps -eo comm | grep -qx kyty_emulator; } # by process name only: never matches this script's own command line (R64)
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0435-$$.new a=$LOCK.0435-$$.aside line
    running && stop "an emulator runs"
    [ ! -L "$E" ] || stop "$E is a link"
    mkdir -p "$R" || stop "cannot make $R"
    line="top exp 0435 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
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
    own || stop "no lock held by 0435"
    running && stop "an emulator runs"
    local f v b bin rc sn sl
    sn=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); sl=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
    (cd "$TREE" && sha256sum -c "$HERE/units.sha256") > "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the shared tree is not the pinned one (patch 59f00d27)"; }
    rm -rf "$S"; mkdir -p "$S/kyty"
    for f in $FILES; do mkdir -p "$S/kyty/$(dirname "$f")"; cp "$TREE/$f" "$S/kyty/$f" || stop "copy $f"; done
    distrobox enter ubuntu -- python3 -I "$HERE/apply0435.py" "$S/kyty" "$HERE/title_settings.hpp" > "$R/apply.out" 2>&1 < /dev/null \
        || { cat "$R/apply.out"; stop "apply0435.py failed on the copies"; }
    [ -s "$S/kyty/src/bc5/title_settings.hpp" ] || stop "no title_settings.hpp in the copies"
    for v in normal lean; do
        b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$E/$v/kyty_emulator
        mkdir -p "$E/$v"; rm -rf "$E/$v/obj" "$E/$v/lib"
        [ -f "$bin" ] && mv "$bin" "$bin.$(md5sum < "$bin" | cut -c1-8)"
        distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$E/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0435.py" emu "$E/$v/compdb.json" "$S/kyty" "$E/$v" "$b" "$bin" \
            $UNITS > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|undefined\|COMPILE FAILED\|AssertionError" "$R/build-$v.out" | head -20
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
        md5sum < "$bin" | cut -d' ' -f1 > "$E/$v/binary.md5"
    done
    for v in normal lean; do
        strings "$E/$v/kyty_emulator" | grep -qxF "KYTY_BC5_TITLE_SETTINGS" || stop "KYTY_BC5_TITLE_SETTINGS is not in $v"
        strings "$E/$v/kyty_emulator" | grep -qF "Title settings (exp 0435)" || stop "the 0435 log line is not in $v"
    done
    echo "private normal $(cat "$E/normal/binary.md5"), lean $(cat "$E/lean/binary.md5")"
    [ "$sn" = "$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1)" ] && [ "$sl" = "$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)" ] \
        || stop "a shared binary changed"
    echo "shared normal $sn, lean $sl: unchanged"
}
case "${1:-}" in
    claim) claim "${2:-private build}" "${3:-20}" ;;
    build) build ;;
    release) release ;;
    *) stop "usage: box0435.sh claim|build|release" ;;
esac
