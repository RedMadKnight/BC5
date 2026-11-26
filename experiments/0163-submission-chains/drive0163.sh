#!/usr/bin/env bash
# BC5 exp 0163 driver: N = run number. Waits for the emulator, samples per-thread CPU from +125 s for 70 s,
# kills at +200 s, keeps stderr and the kernel log tail.
N=$1; cd ~/bc5-work; exec > ~/bc5-work/drive$N.log 2>&1
sudo -n dmesg | tail -3 > dmesg-$N-before.txt
for i in $(seq 1 120); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
P=$(pgrep -x kyty_emulator | head -1); [ -n "$P" ] || { echo "no emulator"; exit 1; }
T0=$(date +%s); echo "emulator $P seen at $(date +%T)"
./cpu-sampler.sh 125 70 cpu-$N.txt &
at() { while [ $(( $(date +%s) - T0 )) -lt $1 ]; do sleep 1; done; }
at 200; pkill -x kyty_emulator; echo "kill at +$(( $(date +%s) - T0 )) s"; sleep 4; pkill -9 -x kyty_emulator; sleep 3
cp play-pkg-last.log run$N-stderr.log; sudo -n dmesg | tail -40 > dmesg-$N-after.txt; echo DONE
