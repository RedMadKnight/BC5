#!/usr/bin/env bash
# BC5 exp 0430: a stand-in test of undo0430b.sh (test_undo0430.sh adapted to its one unit and unchanged archive). A fake
# tree with the unit changed, both binaries changed, a pins file in int0430b.sh's format (PIN_OLD, NORMAL, LEAN, U1, ARCH),
# a fake chain lock include that logs claims, and a pgrep that finds nothing. Cases: alone (claims its own slot), inint
# (UNDO_IN_INT=1: no claim), badpins (U1 missing: refuses, changes nothing), archchanged (the archive differs from the pin:
# the copies are made, the exit says so). Each case's world is a new directory under $1 (kept).
# usage: test_undo0430b.sh <empty scratch directory>
set -u
U=${UNDO:-$(cd "$(dirname "$0")" && pwd)/undo0430b.sh}
BASE=${1:?a scratch directory}
PASS=0; FAIL=0
ok() { if [ "$2" = 1 ]; then PASS=$((PASS + 1)); echo "ok   $1"; else FAIL=$((FAIL + 1)); echo "FAIL $1"; fi; }
m8() { md5sum < "$1" | cut -c1-8; }
world() {
  T=$BASE/$1; mkdir -p "$T/bin" "$T/src/KytyPlus/src/libs" "$T/bc5-work/exp0430/swapb" "$T/bc5-work/exp0413/n" \
    "$T/bc5-work/kytyplus-build/src" "$T/bc5-work/kytyplus-build-lean/src" "$T/cwd" "$T/bc5-work/backend-ubuntu"
  printf '#!/bin/sh\nexit 1\n' > "$T/bin/pgrep"; chmod +x "$T/bin/pgrep"
  printf 'chain_claim() { echo "CLAIM" >> "%s/lock.log"; }\nchain_release() { echo RELEASE >> "%s/lock.log"; }\n' "$T" "$T" > "$T/bc5-work/exp0413/n/chainlock0417.inc"
  K=$T/src/KytyPlus; X=$T/bc5-work/exp0430/swapb
  git -C "$K" init -q; git -C "$K" config core.autocrlf false
  printf 'p0\n' > "$K/src/libs/bc5LleAgc.cpp"
  git -C "$K" add .; git -C "$K" -c user.email=x@y -c user.name=x commit -qm b; git -C "$K" tag f266548
  printf 'p1 ef2ff54f\r\n' > "$K/src/libs/bc5LleAgc.cpp"
  cp "$K/src/libs/bc5LleAgc.cpp" "$X/bc5LleAgc.cpp.before-0430b"
  echo N0 > "$X/kyty_emulator.normal.before-0430b"; echo L0 > "$X/kyty_emulator.lean.before-0430b"
  echo A0 > "$T/bc5-work/backend-ubuntu/libbc5_backend.a"
  { echo "PIN_OLD=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)"; echo "NORMAL=$(m8 "$X/kyty_emulator.normal.before-0430b")"
    echo "LEAN=$(m8 "$X/kyty_emulator.lean.before-0430b")"; echo "U1=$(m8 "$K/src/libs/bc5LleAgc.cpp")"; echo "ARCH=$(m8 "$T/bc5-work/backend-ubuntu/libbc5_backend.a")"; } > "$X/pins.before-0430b"
  P1=$(m8 "$K/src/libs/bc5LleAgc.cpp")
  printf 'p2 bake\r\n' > "$K/src/libs/bc5LleAgc.cpp"
  echo N2 > "$T/bc5-work/kytyplus-build/src/kyty_emulator"; echo L2 > "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator"
}
back() {
  [ "$(m8 "$K/src/libs/bc5LleAgc.cpp")" = "$P1" ] && [ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N0 ] \
    && [ "$(cat "$T/bc5-work/kytyplus-build-lean/src/kyty_emulator")" = L0 ] && echo 1 || echo 0
}
stray() { ls "$T/cwd" | grep -cE '^[0-9a-f]{8}$'; }
run() { (cd "$T/cwd" && HOME=$T PATH=$T/bin:$PATH UNDO_W=$T/bc5-work UNDO_K=$K X=$X "$@" bash "$U" 2>&1); }

world alone
out=$(run env); rc=$?
ok "alone: exit 0 ($out)" "$([ $rc = 0 ] && echo 1)"
ok "alone: the unit and both binaries are back" "$(back)"
ok "alone: no file named by a sum in the working directory" "$([ "$(stray)" = 0 ] && echo 1)"
ok "alone: claimed and released its own slot" "$([ "$(tr '\n' ' ' < "$T/lock.log" 2> /dev/null)" = "CLAIM RELEASE " ] && echo 1)"

world inint
out=$(run env UNDO_IN_INT=1); rc=$?
ok "inint: exit 0" "$([ $rc = 0 ] && echo 1)"
ok "inint: the unit and both binaries are back" "$(back)"
ok "inint: no claim of its own" "$([ ! -e "$T/lock.log" ] && echo 1)"

world badpins
sed -i '/^U1=/d' "$X/pins.before-0430b"
out=$(run env); rc=$?
ok "badpins: refuses ($out)" "$([ $rc != 0 ] && echo 1)"
ok "badpins: changed nothing" "$([ "$(cat "$T/bc5-work/kytyplus-build/src/kyty_emulator")" = N2 ] && [ "$(tr -d '\r' < "$K/src/libs/bc5LleAgc.cpp")" = "p2 bake" ] && echo 1)"

world archchanged
echo A9 > "$T/bc5-work/backend-ubuntu/libbc5_backend.a"
out=$(run env); rc=$?
ok "archchanged: exit not 0 and says the archive ($out)" "$([ $rc != 0 ] && printf '%s' "$out" | grep -q 'the archive is' && echo 1)"
ok "archchanged: the unit and both binaries are back all the same" "$(back)"
echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
