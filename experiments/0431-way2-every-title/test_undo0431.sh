#!/usr/bin/env bash
# BC5 exp 0431: a stand-in test of undo0431.sh (exp 0428's test_undo0428b.sh adapted; LESSONS R10 0425/undo: the pins file's U1=/U2= md5s
# must not overwrite the source paths). A fake tree with both sources changed, both binaries changed, a pins file in int0431.sh's real
# format (PIN_OLD, NORMAL, LEAN, U1, U2, ARCH), a fake chain lock include that logs claims, and a pgrep that finds
# nothing. Cases: alone (claims its own slot), inint (UNDO_IN_INT=1: no claim), badpins (U2 missing: refuses, changes
# nothing). Each case's world is a new directory under $1 (kept; not removed by this script).
# usage: test_undo0431.sh <empty scratch directory>
set -u
U=${UNDO:-$(cd "$(dirname "$0")" && pwd)/undo0431.sh}  # UNDO=<path> tests another version
BASE=${1:?a scratch directory}
PASS=0; FAIL=0
ok() { if [ "$2" = 1 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAIL=$((FAIL + 1)); echo "FAIL $1"; fi; }
m8() { md5sum < "$1" | cut -c1-8; }
world() {
  T=$BASE/$1; mkdir -p "$T/bin" "$T/src/KytyPlus/src/libs" "$T/src/KytyPlus/src/bc5" "$T/bc5-work/exp0431/swap" "$T/bc5-work/exp0413/n" \
    "$T/bc5-work/kytyplus-build/src" "$T/bc5-work/kytyplus-build-lean/src" "$T/cwd"
  printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"; chmod +x "$T/bin/pgrep"
  printf 'chain_claim() { echo "CLAIM" >> "%s/lock.log"; }\nchain_release() { echo RELEASE >> "%s/lock.log"; }\n' "$T" "$T" > "$T/bc5-work/exp0413/n/chainlock0417.inc"
  K=$T/src/KytyPlus; X=$T/bc5-work/exp0431/swap
  git -C "$K" init -q; git -C "$K" config core.autocrlf false
  printf 'p0\n' > "$K/src/libs/bc5LleAgc.cpp"; printf 's0\n' > "$K/src/bc5/switch_defaults.hpp"
  git -C "$K" add .; git -C "$K" -c user.email=x@y -c user.name=x commit -qm b; git -C "$K" tag f266548
  printf 'p1 700fd4c2\r\n' > "$K/src/libs/bc5LleAgc.cpp"; printf 's1 700fd4c2\n' > "$K/src/bc5/switch_defaults.hpp"
  cp "$K/src/libs/bc5LleAgc.cpp" "$X/bc5LleAgc.cpp.before-0431"; cp "$K/src/bc5/switch_defaults.hpp" "$X/switch_defaults.hpp.before-0431"
  echo N0 > "$X/kyty_emulator.normal.before-0431"; echo L0 > "$X/kyty_emulator.lean.before-0431"
  { echo "PIN_OLD=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)"; echo "NORMAL=$(m8 "$X/kyty_emulator.normal.before-0431")"
    echo "LEAN=$(m8 "$X/kyty_emulator.lean.before-0431")"; echo "U1=$(m8 "$K/src/libs/bc5LleAgc.cpp")"; echo "U2=$(m8 "$K/src/bc5/switch_defaults.hpp")"; echo "ARCH=9aab722c"; } > "$X/pins.before-0431"
  P1=$(m8 "$K/src/libs/bc5LleAgc.cpp"); P2=$(m8 "$K/src/bc5/switch_defaults.hpp")
  printf 'p2 w2\r\n' > "$K/src/libs/bc5LleAgc.cpp"; printf 's2 w2\n' > "$K/src/bc5/switch_defaults.hpp"
  echo N2 > "$T/bc5-work/kytyplus-build/src/kyty_emulator"; echo L2 > "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator"
}
back() {  # 1 if both sources and both binaries are the before-copies
  [ "$(m8 "$K/src/libs/bc5LleAgc.cpp")" = "$P1" ] && [ "$(m8 "$K/src/bc5/switch_defaults.hpp")" = "$P2" ] \
    && [ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N0 ] && [ "$(cat "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator")" = L0 ] && echo 1 || echo 0
}
stray() { ls "$T/cwd" | grep -cE '^[0-9a-f]{8}$'; }

world alone
out=$(cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH bash "$U" 2>&1); rc=$?
ok "alone: exit 0 ($out)" "$([ $rc = 0 ] && echo 1)"
ok "alone: both sources and both binaries are back" "$(back)"
ok "alone: no file named by a sum in the working directory" "$([ "$(stray)" = 0 ] && echo 1)"
ok "alone: claimed and released its own slot" "$([ "$(tr '\n' ' ' < "$T/lock.log" 2> /dev/null)" = "CLAIM RELEASE " ] && echo 1)"

world inint
out=$(cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH UNDO_IN_INT=1 bash "$U" 2>&1); rc=$?
ok "inint: exit 0" "$([ $rc = 0 ] && echo 1)"
ok "inint: both sources and both binaries are back" "$(back)"
ok "inint: no claim of its own" "$([ ! -e "$T/lock.log" ] && echo 1)"

world badpins
sed -i '/^U2=/d' "$X/pins.before-0431"
out=$(cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH bash "$U" 2>&1); rc=$?
ok "badpins: refuses ($out)" "$([ $rc != 0 ] && echo 1)"
ok "badpins: changed nothing" "$([ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N2 ] && [ "$(tr -d '\r' < "$K/src/libs/bc5LleAgc.cpp")" = "p2 w2" ] && echo 1)"
echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
