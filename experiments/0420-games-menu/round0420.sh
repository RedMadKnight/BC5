#!/usr/bin/env bash
# BC5 exp 0420: the one build round on the box (CPU only, no emulator, one lock line). Kit: ~/bc5-work/exp0420/kit
# (this script, mkmenu0420.py, games_list.hpp, ed0419g.py, the tools tarball, the launchers, the tests).
#   1. bc5-mount from this branch: cargo test and the release build in the ubuntu distrobox (its cargo has no fmt and no
#      clippy: those ran on the laptop, for Windows and for the Linux target, and run in CI),
#      into ~/bc5-work/exp0420/bc5-tools (the shared ~/bc5-work/bc5-tools-ubuntu is not touched)
#   2. the launcher's tests on the box (real pgrep, Linux): test-play-any.sh
#   3. the menu: mkmenu0420.py on the private tree (exp0413/p/tree, at build W), normal and lean rebuilt; the files
#      it changes are saved first to $P/p5-before/ with W's binaries
# usage (on the box): round0420.sh [mount|tests|menu|all]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; X=$W/exp0420; K=$X/kit
STEP=${1:-all}
pgrep '^kyty_emulator' > /dev/null && { echo "round0420: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0420: bc5-mount build and tests, the launcher's tests, the menu applied to the private tree and one rebuild (CPU only, no emulator)" 40 || { echo "round0420: NOT STARTED"; exit 1; }
trap chain_release EXIT
mkdir -p "$X/src" "$X/bc5-tools"
if [ "$STEP" = all ] || [ "$STEP" = mount ]; then
    rm -rf "${X:?}/src/tools" && tar -xzf "$K/tools.tgz" -C "$X/src" || { echo "round0420 STOP: cannot unpack the tools"; exit 1; }
    echo "== $(date +%T) bc5-mount: test, build"
    distrobox enter ubuntu -- sh -c "cd '$X/src/tools/bc5-mount' && CARGO_TARGET_DIR='$X/bc5-tools' nice -n 19 cargo test 2>&1 | grep -E '^test result|FAILED|panicked' && CARGO_TARGET_DIR='$X/bc5-tools' nice -n 19 cargo build --release" < /dev/null > "$X/mount.log" 2>&1
    rc=$?
    grep -E '^test result|FAILED|panicked|^error|warning: unused' "$X/mount.log" | cut -c1-200
    [ "$rc" = 0 ] || { echo "round0420 STOP: bc5-mount (see $X/mount.log)"; exit 1; }
    echo "bc5-mount: $(md5sum < "$X/bc5-tools/release/bc5-mount" | cut -c1-8) at $X/bc5-tools/release/bc5-mount; uninstall: $("$X/bc5-tools/release/bc5-mount" uninstall --help > /dev/null 2>&1 && echo present)"
fi
if [ "$STEP" = all ] || [ "$STEP" = tests ]; then
    echo "== $(date +%T) the launcher's tests"
    bash "$K/test-play-any.sh" 2>&1 | tail -16
fi
if [ "$STEP" = all ] || [ "$STEP" = menu ]; then
    F="src/graphics/presentation/hostMenu.cpp src/bc5/games_list.hpp"
    if [ -d "$P/p5-before" ]; then
        echo "putting W's files back first"
        cp -p "$P/p5-before/src/graphics/presentation/hostMenu.cpp" "$P/tree/src/graphics/presentation/hostMenu.cpp" && rm -f "$P/tree/src/bc5/games_list.hpp"
    else
        mkdir -p "$P/p5-before/src/graphics/presentation" "$P/p5-before/bin" && cp -p "$P/tree/src/graphics/presentation/hostMenu.cpp" "$P/p5-before/src/graphics/presentation/" &&
            cp -p "$P/build-normal/src/kyty_emulator" "$P/p5-before/bin/kyty_emulator.normal" && cp -p "$P/build-lean/src/kyty_emulator" "$P/p5-before/bin/kyty_emulator.lean" || { echo "round0420 STOP: cannot save"; exit 1; }
    fi
    [ "$(md5sum < "$P/tree/src/graphics/presentation/hostMenu.cpp" | cut -c1-8)" = 53c61393 ] || { echo "round0420 STOP: hostMenu.cpp is not W's (53c61393)"; exit 1; }
    mkdir -p "$K/0419-switch-cleanup" && cp "$K/ed0419g.py" "$K/0419-switch-cleanup/" && mkdir -p "$K/0420-games-menu" && cp "$K/mkmenu0420.py" "$K/games_list.hpp" "$K/0420-games-menu/" || exit 1
    python3 "$K/0420-games-menu/mkmenu0420.py" "$P/tree" || { echo "round0420 STOP: the generator refused"; exit 1; }
    for f in $F; do echo "  $(md5sum < "$P/tree/$f" | cut -c1-8)  $f"; done
    for v in normal lean; do
        d=$P/build-$v
        echo "== $(date +%T) build $v"
        if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$d.build.log" 2>&1; then
            grep -m12 -E "error:" "$d.build.log" | cut -c1-260
            echo "round0420 STOP: build $v failed"
            exit 1
        fi
        echo "$v: $(md5sum < "$d/src/kyty_emulator" | cut -d' ' -f1), warnings $(grep -c 'warning:' "$d.build.log"), in hostMenu.cpp: $(grep 'hostMenu.cpp.*warning:' "$d.build.log" | cut -c1-160 | head -3)"
    done
fi
echo "round0420 done $(date +%T)"
