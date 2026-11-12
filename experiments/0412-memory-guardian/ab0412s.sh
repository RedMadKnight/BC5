#!/usr/bin/env bash
# BC5 exp 0412 (README section 37): the runs for BC5_GUARD_NOGPU_UNPIN (build g412s), one after another: arm fast2 on
# the scripted load with one heap without a GPU bit left unpinned, then the next, then all four; RT on; measuring
# watchdog 220 MiB; the fuse as always. After each run the journal's lines of the trial, the ledger and any fault or
# timeout line go to raw/<tag>-nogpu.txt. THE CHAIN STOPS after a run with a kernel line (a GPU ring timeout or
# fault): the heap of that run is one the GPU needs. A file night/STOP ends the chain between runs.
# usage (on the box, under setsid nohup): ab0412s.sh
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
calm() { for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
one() { # tag heaps
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $1"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $1"; exit 1; }
  pgrep steamwebhelper > /dev/null && { echo "$(date +%T) chain: Steam runs: stopped before $1"; exit 1; }
  sleep 10
  N_WD_MIB=220 bash "$X/run0412n.sh" "$1" fast2 60 "BC5_GUARD_NOGPU_UNPIN=$2" > "$N/run-$1.log" 2>&1
  J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  grep -a 'guard nogpu\|^guard: t\|^guard heaps\|learned: fault\|FAILED\|TIMEOUT\|timed out\|^direct: [0-9]* views' "$J" | cut -c1-500 > "$N/raw/$1-nogpu.txt"
  echo "$(date +%T) chain: $1 ($2): $(cut -c1-190 "$N/raw/$1-summary.txt" 2> /dev/null)"
  if [ -s "$N/raw/$1-dmesg-after.txt" ]; then echo "$(date +%T) chain: kernel lines after $1: stopped"; exit 0; fi
}
one f0base -
one f1phys Physics
one f2comp ComponentHeap
one f3dyn DynamicHeap
one f4init InitAllocator
one f5all Physics,ComponentHeap,DynamicHeap,InitAllocator
echo "$(date +%T) chain: end"
