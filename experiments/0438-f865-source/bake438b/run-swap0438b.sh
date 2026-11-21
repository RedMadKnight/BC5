#!/usr/bin/env bash
# BC5 exp 0438 (tag bake438b; as run-swap0438o.sh): swap0438b.sh, then smoke0438bs.sh on the swapped binaries; one unit under
# the user manager (R65), so the smoke's emulators get rtkit. Writes swap.log and swap.done (the swap's exit code, or the
# smoke's) beside this script.
# usage (on the box): systemd-run --user --unit=bc5-0438b-swap --collect -p WorkingDirectory=$HOME/bc5-work/exp0438/bake438b \
#                       sh -c 'PATCH_NEW=<md5> bash run-swap0438b.sh > swap.log 2>&1; echo $? > swap.done'
set -u
ulimit -c 0
HERE=$(cd "$(dirname "$0")" && pwd); W=$HOME/bc5-work
echo "run-swap0438b $(date +%T): boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
# one BOX-LOCK line for the swap and the smoke: swap0438b.sh and smoke0438bs.sh take it over
. "$W/exp0413/n/chainlock0417.inc"
chain_claim "exp 0438: the bake438b swap (A1+A1P, A2, the acb gate; patch 0fede35d -> ${PATCH_NEW:-?}, archive, normal and lean rebuilt) and its smoke (ASTRO BOT lean 200 s + normal 200 s)" 75 || { echo "run-swap0438b: no lock"; exit 1; }
bash "$HERE/swap0438b.sh" || { echo "run-swap0438b: swap0438b failed: no smoke"; exit 1; }
MN=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); ML=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
cd "$W/exp0413/n" || exit 1
NORMAL_WANT=$MN LEAN_WANT=$ML bash "$HERE/smoke0438bs.sh"
r=$?; echo "run-swap0438b $(date +%T): smoke exit $r"; exit $r
