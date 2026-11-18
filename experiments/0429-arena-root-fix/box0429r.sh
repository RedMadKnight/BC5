#!/usr/bin/env bash
# BC5 exp 0429, the private builds for the R swap (box0429.sh's build, on the shared tree at patch 940e8f36):
#   box0429r.sh build swap   the swap form (mkswap0429r.py, no option): normal and lean, ~/bc5-work/exp0429/rs/{normal,lean}
#   box0429r.sh build test   the stressed pair's build: --keep-slice --stressor, normal only, ~/bc5-work/exp0429/rt/normal
# The units come from ~/src/KytyPlus (read only); the three edited ones are checked against pins-swap0429r.txt by
# mkswap0429r.py. switch_defaults.hpp is included by pthread.cpp, main.cpp and libs/libAmpr.cpp, so those two are
# compiled from the private copy too. Lock: box0429.sh claim/release (the caller's). Nothing shared is written.
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0429; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
stop() { echo "0429r STOP: $*"; exit 1; }
[ "${1:-}" = build ] || stop "usage: box0429r.sh build swap|test"
V=${2:-}; case "$V" in swap) D=$E/rs; FL=""; VARS="normal lean" ;; test) D=$E/rt; FL="--keep-slice --stressor"; VARS="normal" ;; *) stop "swap or test" ;; esac
[ -s "$E/lock.line" ] && [ "$(cat "$W/BOX-LOCK" 2> /dev/null)" = "$(cat "$E/lock.line")" ] || stop "no lock held by 0429"
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = 940e8f36 ] || stop "the shared tree is not patch 940e8f36"
S=$D/src; R=$D/raw
rm -rf "$S"; mkdir -p "$S" "$R"
for u in src/kernel/pthread.cpp src/kernel/semaphore.cpp src/bc5/switch_defaults.hpp src/main.cpp src/libs/libAmpr.cpp \
         src/loader/gamePatch.cpp src/loader/runtimeLinker.cpp src/graphics/presentation/hostMenu.cpp src/graphics/presentation/window/hostInput.cpp; do
    mkdir -p "$S/$(dirname "$u")"; cp "$K/$u" "$S/$u" || stop "copy $u"
done
# shellcheck disable=SC2086
python3 -I "$HERE/mkswap0429r.py" "$S" $FL > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; stop "mkswap0429r failed"; }
cat "$R/patch.out"
for v in $VARS; do
    b=$W/kytyplus-build$([ $v = lean ] && echo -lean); bin=$D/$v/kyty_emulator
    mkdir -p "$D/$v"; rm -rf "$D/$v/obj"
    [ -f "$bin" ] && mv "$bin" "$bin.$(md5sum < "$bin" | cut -c1-8)"
    distrobox enter ubuntu -- sh -c "cd '$b' && ninja -t compdb -x" > "$D/$v/compdb.json" 2> "$R/compdb-$v.err" < /dev/null || stop "compdb $v failed"
    distrobox enter ubuntu -- env LC_ALL=C LANGUAGE=C python3 -I "$HERE/build0429.py" "$D/$v/compdb.json" "$S" "$D/$v" "$b" "$bin" \
        src/main.cpp src/libs/libAmpr.cpp > "$R/build-$v.out" 2>&1 < /dev/null
    rc=$?; echo "$v: build rc $rc; errors $(grep -c 'error:' "$R/build-$v.out"); warnings $(grep -c 'warning:' "$R/build-$v.out")"
    grep -n "error:\|warning:\|undefined\|COMPILE FAILED" "$R/build-$v.out" | head -20
    [ "$rc" = 0 ] && [ -x "$bin" ] || stop "build $v failed: $R/build-$v.out"
    md5sum < "$bin" | cut -d' ' -f1 > "$D/$v/binary.md5"
    echo "$v: $bin $(cut -c1-8 "$D/$v/binary.md5")"
done
echo "box0429r build $V done $(date +%T)"
