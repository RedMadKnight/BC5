#!/usr/bin/env bash
# BC5 exp 0429: a stand-in test of undo0429.sh (exp 0431's test_undo0431.sh adapted). A fake tree (git, tag f266548) with
# three units changed and one deleted (as mkswap0429.py does), both binaries changed, input.cfg without its JobArenaFix
# line, a pins file in int0429.sh's real format (PIN_OLD, NORMAL, LEAN, ARCH, CFG_MD5, UNIT lines, CFG_NEW), a fake chain
# lock include that logs claims, and a pgrep that finds nothing. Cases:
#   alone    claims its own slot; units, the deleted file, binaries and input.cfg (copy) back
#   inint    UNDO_IN_INT=1: no claim
#   badpins  LEAN missing: refuses, changes nothing
#   nocopy   a unit's copy missing: refuses, changes nothing
#   menu     input.cfg changed since the swap (the menu wrote it): the other lines kept, the JobArenaFix line added back
#   early    no CFG_NEW (int failed before step 6): input.cfg untouched
# usage: test_undo0429.sh <empty scratch directory>
set -u
U=${UNDO:-$(cd "$(dirname "$0")" && pwd)/undo0429.sh}
BASE=${1:?a scratch directory}
PASS=0; FAIL=0
ok() { if [ "$2" = 1 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAIL=$((FAIL + 1)); echo "FAIL $1"; fi; }
m8() { md5sum < "$1" | cut -c1-8; }
UNITS="src/loader/gamePatch.cpp src/kernel/pthread.cpp src/graphics/presentation/window/hostInput.h src/bc5/job_arena_fix.hpp"
world() {
  T=$BASE/$1; mkdir -p "$T/bin" "$T/src/KytyPlus" "$T/bc5-work/exp0429/swap/units" "$T/bc5-work/exp0413/n" \
    "$T/bc5-work/kytyplus-build/src" "$T/bc5-work/kytyplus-build-lean/src" "$T/cwd"
  printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"; chmod +x "$T/bin/pgrep"
  printf 'chain_claim() { echo "CLAIM" >> "%s/lock.log"; }\nchain_release() { echo RELEASE >> "%s/lock.log"; }\n' "$T" "$T" > "$T/bc5-work/exp0413/n/chainlock0417.inc"
  K=$T/src/KytyPlus; X=$T/bc5-work/exp0429/swap; CFG=$T/bc5-work/input.cfg
  git -C "$K" init -q; git -C "$K" config core.autocrlf false
  for u in $UNITS; do mkdir -p "$K/$(dirname "$u")"; done
  printf 'g0\n' > "$K/src/loader/gamePatch.cpp"; printf 't0\n' > "$K/src/kernel/pthread.cpp"; printf 'h0\n' > "$K/src/graphics/presentation/window/hostInput.h"
  git -C "$K" add .; git -C "$K" -c user.email=x@y -c user.name=x commit -qm b; git -C "$K" tag f266548
  # the shared state before the swap (patch "9e7c4514"): the units changed, the header added
  printf 'g1 hook\r\n' > "$K/src/loader/gamePatch.cpp"; printf 't1 JobArenaFix\n' > "$K/src/kernel/pthread.cpp"
  printf 'h1 JobArenaFix\n' > "$K/src/graphics/presentation/window/hostInput.h"; printf 'j1\n' > "$K/src/bc5/job_arena_fix.hpp"
  git -C "$K" add -N src/bc5/job_arena_fix.hpp
  printf 'Pad=1\nRayTracing.TITLE2=on\nJobArenaFix.TITLE2=off\nScale=2\n' > "$CFG"
  for u in $UNITS; do cp -p "$K/$u" "$X/units/$(basename "$u").before-0429"; done
  echo N0 > "$X/kyty_emulator.normal.before-0429"; echo L0 > "$X/kyty_emulator.lean.before-0429"; cp -p "$CFG" "$X/input.cfg.before-0429"
  PIN=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
  { echo "PIN_OLD=$PIN"; echo "NORMAL=$(m8 "$X/kyty_emulator.normal.before-0429")"; echo "LEAN=$(m8 "$X/kyty_emulator.lean.before-0429")"
    echo "ARCH=1423af83"; echo "CFG_MD5=$(m8 "$CFG")"; for u in $UNITS; do echo "UNIT $(m8 "$K/$u") $u"; done; } > "$X/pins.before-0429"
  # the swap
  printf 'g0\n' > "$K/src/loader/gamePatch.cpp"; printf 't2\n' > "$K/src/kernel/pthread.cpp"; printf 'h2\n' > "$K/src/graphics/presentation/window/hostInput.h"
  rm "$K/src/bc5/job_arena_fix.hpp"
  grep -v '^JobArenaFix\.' "$X/input.cfg.before-0429" > "$CFG"; echo "CFG_NEW=$(m8 "$CFG")" >> "$X/pins.before-0429"
  echo N2 > "$T/bc5-work/kytyplus-build/src/kyty_emulator"; echo L2 > "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator"
}
run() { out=$(cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH "$@" bash "$U" 2>&1); rc=$?; }
back() {  # 1 if the units, the header, the tree's diff and both binaries are as before the swap
  for u in $UNITS; do [ "$(m8 "$K/$u" 2> /dev/null)" = "$(grep " $u\$" "$X/pins.before-0429" | cut -d' ' -f2)" ] || { echo 0; return; }; done
  [ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = "$PIN" ] && [ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N0 ] \
    && [ "$(cat "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator")" = L0 ] && echo 1 || echo 0
}
untouched() { [ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N2 ] && [ ! -e "$K/src/bc5/job_arena_fix.hpp" ] && [ "$(cat "$K/src/kernel/pthread.cpp")" = t2 ] && echo 1 || echo 0; }

world alone; run env
ok "alone: exit 0 ($out)" "$([ $rc = 0 ] && echo 1)"
ok "alone: units, header, diff and binaries back" "$(back)"
ok "alone: input.cfg is the copy" "$([ "$(m8 "$CFG")" = "$(m8 "$X/input.cfg.before-0429")" ] && echo 1)"
ok "alone: claimed and released its own slot" "$([ "$(tr '\n' ' ' < "$T/lock.log" 2> /dev/null)" = "CLAIM RELEASE " ] && echo 1)"
ok "alone: no stray file in the working directory" "$([ -z "$(ls "$T/cwd")" ] && echo 1)"

world inint; run env UNDO_IN_INT=1
ok "inint: exit 0" "$([ $rc = 0 ] && echo 1)"
ok "inint: back" "$(back)"
ok "inint: no claim of its own" "$([ ! -e "$T/lock.log" ] && echo 1)"

world badpins; sed -i '/^LEAN=/d' "$X/pins.before-0429"; run env
ok "badpins: refuses ($out)" "$([ $rc != 0 ] && echo 1)"
ok "badpins: changed nothing" "$(untouched)"

world nocopy; rm "$X/units/pthread.cpp.before-0429"; run env
ok "nocopy: refuses ($out)" "$([ $rc != 0 ] && echo 1)"
ok "nocopy: changed nothing" "$(untouched)"

world menu; echo 'Volume=7' >> "$CFG"; run env
ok "menu: exit 0 ($out)" "$([ $rc = 0 ] && echo 1)"
ok "menu: the menu's line kept and the JobArenaFix line back" "$(grep -qx 'Volume=7' "$CFG" && grep -qx 'JobArenaFix.TITLE2=off' "$CFG" && [ "$(grep -c JobArenaFix "$CFG")" = 1 ] && echo 1)"

world early; sed -i '/^CFG_NEW=/d' "$X/pins.before-0429"; c0=$(m8 "$CFG"); run env
ok "early: exit 0" "$([ $rc = 0 ] && echo 1)"
ok "early: input.cfg untouched" "$([ "$(m8 "$CFG")" = "$c0" ] && echo 1)"
ok "early: back" "$(back)"
echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
