#!/usr/bin/env bash
# BC5 exp 0434: int0434.sh, then smoke0434.sh on the swapped binaries; one unit under the user manager (R65), so the
# smoke's emulators get rtkit. Writes swap.log and swap.done (int's exit code, or the smoke's) beside this script.
# usage (on the box): systemd-run --user --unit=bc5-0434-swap --collect -p WorkingDirectory=$HOME/bc5-work/exp0434/bake \
#                       sh -c 'PATCH_NEW=<md5> bash run-swap0434.sh > swap.log 2>&1; echo $? > swap.done'
set -u
ulimit -c 0
HERE=$(cd "$(dirname "$0")" && pwd); W=$HOME/bc5-work
echo "run-swap0434 $(date +%T): boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
bash "$HERE/int0434.sh" || { echo "run-swap0434: int0434 failed: no smoke"; exit 1; }
MN=$(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -d' ' -f1); ML=$(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -d' ' -f1)
cd "$W/exp0413/n" || exit 1
NORMAL_WANT=$MN LEAN_WANT=$ML bash "$HERE/smoke0434.sh"
r=$?; echo "run-swap0434 $(date +%T): smoke exit $r"; exit $r
