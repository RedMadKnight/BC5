#!/usr/bin/env bash
# BC5 (experiment 0203): wait for the box, then start run0203-opening.sh <tag> <secs>. This follows the top
# session's conditional grant: the box must be free (no BOX-LOCK, no kyty_emulator), the boot id unchanged (no
# reboot since the grant), the last session's journal must have no TIMEOUT, and the kernel log no new amdgpu
# error. If any of these fails it starts nothing and says why. Run detached:
#   setsid nohup wait0203.sh <tag> <secs> <boot id prefix> > raw/<tag>-wait.out 2>&1 &
set -u
TAG=${1:?tag}; SECS=${2:-600}; BOOT=${3:?boot id prefix}
E=$HOME/bc5-work/exp0203
N0=$(sudo -n dmesg 2> /dev/null | wc -l)
for _ in $(seq 1 360); do  # up to an hour
  if [ ! -s ~/bc5-work/BOX-LOCK ] && ! pgrep -x kyty_emulator > /dev/null; then
    sleep "${GRACE:-20}"  # a session may start its next arm right after its last one (GRACE s, default 20)
    [ ! -s ~/bc5-work/BOX-LOCK ] && ! pgrep -x kyty_emulator > /dev/null && break
  fi
  sleep 10
done
echo "box free at $(date +%T)"
[ -s ~/bc5-work/BOX-LOCK ] && { echo "still locked: $(cat ~/bc5-work/BOX-LOCK); nothing started"; exit 1; }
B=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
[ "$B" = "$BOOT" ] || { echo "boot id $B, not $BOOT: the box rebooted; nothing started"; exit 1; }
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
T=$(dd if="$J" iflag=direct bs=4M 2> /dev/null | grep -a -c "TIMEOUT")
[ "$T" = 0 ] || { echo "$T TIMEOUT lines in $J: nothing started"; exit 1; }
K=$(sudo -n dmesg 2> /dev/null | tail -n +"$((N0 + 1))" | grep -ci "amdgpu.*\(fault\|timeout\|reset\|error\)")
[ "$K" = 0 ] || { echo "$K new amdgpu error lines in the kernel log: nothing started"; exit 1; }
echo "conditions hold ($J clean, boot $B): starting $TAG"
exec "$E/run0203-opening.sh" "$TAG" "$SECS"
