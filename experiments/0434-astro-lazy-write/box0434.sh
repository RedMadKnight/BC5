#!/bin/bash
# BC5 experiment 0434: the ONE combined private test build of ud434 (BC5_DIRECT_UD_TARGETS, this experiment) and exp 0435's
# per-title settings (KYTY_BC5_TITLE_SETTINGS, branch exp/0435-per-game-settings, its kit apply0435.py) on the BC-250.
#   box0434.sh build <md5>  copies of the shared tree's files (patch 59f00d27; 0435's units.sha256 and bc5LleAgc.cpp 8eb42a10)
#                           into ~/bc5-work/exp0434/src, apply0435.py on the copies, the patched bc5LleAgc.cpp (uploaded
#                           beside this script as bc5LleAgc.cpp, md5 <md5>) put in; the 4 changed units compiled with the
#                           shared normal and the shared lean build's own commands and relinked with their objects
#                           otherwise (CPU only, nice 19): ~/bc5-work/exp0434/{normal,lean}/kyty_emulator; the test
#                           launcher ~/bc5-work/exp0434/play-test.sh (play-any.sh with BC5_EMU/BC5_EMU_LEAN set to them)
#   box0434.sh release      clears the lock only if it holds this experiment's exact line
# Nothing shared is written: ~/src/KytyPlus, the shared builds, the patch and the launchers are only read; their md5s are
# taken before and after. Beside this script: build0434.py, bc5LleAgc.cpp, apply0435.py, title_settings.hpp, units.sha256.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0434; R=$E/raw; S=$E/src; LOCK=$W/BOX-LOCK; ID=$E/lock.line
HERE=$(cd "$(dirname "$0")" && pwd)
T=$HOME/src/KytyPlus
FILES0435="src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/hostInput.h src/graphics/presentation/window.h src/graphics/presentation/window/window.cpp src/bc5/switch_defaults.hpp src/main.cpp"
EXTRA_UNITS="src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/window.cpp src/main.cpp"
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
    if ps -eo comm= | grep -qx kyty_emulator; then echo "an emulator runs: stop"; exit 3; fi
    if [ -s "$LOCK" ]; then echo "BOX-LOCK holds a line, one holder at a time:"; cat "$LOCK"; exit 3; fi
}
shared_md5s() { # the shared things this build must not change
    for f in $FILES0435 src/libs/bc5LleAgc.cpp; do echo "tree $f $(m8 "$T/$f")"; done
    echo "normal $(m8 "$W/kytyplus-build/src/kyty_emulator")"; echo "lean $(m8 "$W/kytyplus-build-lean/src/kyty_emulator")"
    echo "archive $(m8 "$W/backend-ubuntu/libbc5_backend.a")"
    for f in play-any.sh play-astro.sh play-pkg.sh lean-session.sh input.cfg; do echo "$f $(m8 "$W/$f")"; done
}
case "${1:-}" in
build)
    want=${2:?md5 of the patched bc5LleAgc.cpp}
    guard
    mkdir -p "$R"
    line="exp0434 combined private build ud434 + 0435 (CPU only, nice 19) | $(date '+%F %T') | ~20 min"
    echo "$line" > "$ID"; echo "$line" >> "$LOCK"
    shared_md5s > "$R/shared-before.txt"; cat "$R/shared-before.txt"
    [ "$(m8 "$T/src/libs/bc5LleAgc.cpp")" = 8eb42a10 ] || stop "the shared tree's bc5LleAgc.cpp is not 8eb42a10 (patch 59f00d27)"
    (cd "$T" && sha256sum -c "$HERE/units.sha256") > "$R/units.txt" 2>&1 || { cat "$R/units.txt"; stop "the shared tree is not 0435's pinned one"; }
    [ "$(md5sum "$HERE/bc5LleAgc.cpp" | cut -d' ' -f1)" = "$want" ] || stop "the uploaded bc5LleAgc.cpp is not $want"
    rm -rf "$S"; mkdir -p "$S/src/libs"
    for f in $FILES0435; do mkdir -p "$S/$(dirname "$f")"; cp "$T/$f" "$S/$f" || stop "copy $f"; done
    distrobox enter ubuntu -- python3 -I "$HERE/apply0435.py" "$S" "$HERE/title_settings.hpp" > "$R/apply0435.out" 2>&1 < /dev/null \
        || { cat "$R/apply0435.out"; stop "apply0435.py failed on the copies"; }
    cat "$R/apply0435.out"
    cp "$HERE/bc5LleAgc.cpp" "$S/src/libs/bc5LleAgc.cpp"
    (cd "$S" && find . -type f | sort | xargs md5sum) > "$R/src-md5.txt"; cat "$R/src-md5.txt"
    for v in normal lean; do
        B=$W/kytyplus-build; [ "$v" = lean ] && B=$W/kytyplus-build-lean
        OUT=$E/$v; mkdir -p "$OUT"
        echo "== $v: shared binary $(m8 "$B/src/kyty_emulator") in $B"
        distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$OUT/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb failed ($v)"
        bin=$OUT/kyty_emulator
        [ -f "$bin" ] && mv "$bin" "$bin.$(m8 "$bin")"
        distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0434.py" "$OUT/compdb.json" "$S" "$OUT" "$B" "$bin" $EXTRA_UNITS > "$R/build-$v.out" 2>&1 < /dev/null
        rc=$?; echo "$v build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
        grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -30
        [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build failed: $R/build-$v.out"
        strings "$bin" > "$OUT/strings.txt"
        echo "$v: $bin $(m8 "$bin"); 'tag ud434' $(grep -c 'tag ud434' "$OUT/strings.txt"); BC5_DIRECT_UD_TARGETS $(grep -c 'BC5_DIRECT_UD_TARGETS' "$OUT/strings.txt"); KYTY_BC5_TITLE_SETTINGS $(grep -c 'KYTY_BC5_TITLE_SETTINGS' "$OUT/strings.txt")"
    done
    cat > "$E/play-test.sh" <<'LAUNCH'
#!/bin/bash
# exp 0434 + 0435 combined private test build: the shared launcher play-any.sh, unchanged, with the private binaries.
# BC5_DIRECT_UD_TARGETS=0 turns ud434 off, KYTY_BC5_TITLE_SETTINGS=0 turns 0435 off (no build needed for either).
export BC5_EMU=$HOME/bc5-work/exp0434/normal/kyty_emulator
export BC5_EMU_LEAN=$HOME/bc5-work/exp0434/lean/kyty_emulator
exec "$HOME/bc5-work/play-any.sh" "$@"
LAUNCH
    chmod +x "$E/play-test.sh"; echo "launcher: $E/play-test.sh $(m8 "$E/play-test.sh")"
    shared_md5s > "$R/shared-after.txt"
    if cmp -s "$R/shared-before.txt" "$R/shared-after.txt"; then echo "shared md5s unchanged"; else echo "SHARED MD5S CHANGED:"; diff "$R/shared-before.txt" "$R/shared-after.txt"; fi
    release
    ;;
release) release ;;
*) echo "usage: $0 build <md5> | release"; exit 2 ;;
esac
