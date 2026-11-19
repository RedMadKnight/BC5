#!/usr/bin/env bash
# BC5 exp 0433: int0433.sh, then smoke0433.sh on the swapped binaries; one unit under the user manager (R65), so the
# smoke's emulators get rtkit. Writes swap.log and swap.done (int's exit code, or the smoke's) beside this script.
# usage (on the box): systemd-run --user --unit=bc5-0433-swap --collect -p WorkingDirectory=$HOME/bc5-work/exp0433/bake \
#                       sh -c 'bash run-swap0433.sh > swap.log 2>&1; echo $? > swap.done'
set -u
ulimit -c 0
HERE=$(cd "$(dirname "$0")" && pwd); W=$HOME/bc5-work
echo "run-swap0433 $(date +%T): boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
bash "$HERE/int0433.sh" || { echo "run-swap0433: int0433 failed: no smoke"; exit 1; }
MN=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); ML=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
cd "$W/exp0413/n" || exit 1
NORMAL_WANT=$MN LEAN_WANT=$ML bash "$HERE/smoke0433.sh"
r=$?; echo "run-swap0433 $(date +%T): smoke exit $r"; exit $r
