#!/usr/bin/env bash
# BC5 experiment 0252 (exp 0249's runarm0249.sh): the private binary with the tiler scratch pool, arm OLD (pool off) or
# NEW (KYTY_BC5_TILER_POOL=1), KYTY_BC5_VMA_TRACE=1 in both (counts the scratch allocations); the thread sampler, no stack watcher. Laptop side of one bench arm: streams the box's kernel log into the experiment's raw/
# (ending by itself once the run's lock is gone and no emulator runs, capped at 15 min), runs the box's bench script,
# and stops the run's emulator at the first amdgpu page fault or ring timeout (B and C remove the compaction skip).
# usage: runarm0252.sh <NNNN> <tag> <A|B|C>
N=$1; TAG=$2; ARM=$3
D=/c/Users/kjani/Downloads/bc5/bc5/experiments/$N-tiler-scratch-pool/raw
K=$D/kernel-$TAG.txt
COMMON="BC5_EMU=/home/kjaniszewski/bc5-work/exp0252/kyty_emulator KYTY_BC5_VMA_TRACE=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_TIMEOUT_PROBE=1"
case $ARM in
  OLD) SKIP=909974400; POOL="" ;;
  NEW) SKIP=909974400; POOL="KYTY_BC5_TILER_POOL=1" ;;
  *) echo "arm OLD or NEW"; exit 1 ;;
esac
ssh bc250 "pgrep '^kyty_emulator' >/dev/null && { echo emulator running; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { cat ~/bc5-work/BOX-LOCK; exit 1; }; [ -e ~/bc5-work/exp0194/r-$TAG ] && { echo tag used; exit 1; }; exit 0" || exit 1
# kernel stream: the box side ends 30 s after the run's lock is gone and no emulator runs (at the earliest after 90 s)
ssh -o ServerAliveInterval=30 bc250 "
  journalctl -k -f -o short-iso-precise --since -5s & jp=\$!
  end=\$(( \$(date +%s) + 900 )); sleep 90
  while [ \$(date +%s) -lt \$end ]; do
    grep -q 'exp $N | bench $TAG ' ~/bc5-work/BOX-LOCK 2>/dev/null || pgrep '^kyty_emulator' >/dev/null || break
    sleep 10
  done
  sleep 30; kill \$jp" >> "$K" 2>&1 &
KP=$!
sleep 3
# fault watch: the first amdgpu page fault or ring timeout of this run stops its emulator (the bench then drops its lock)
( for _ in $(seq 1 900); do
    if grep -q -E "amdgpu.*(page fault|ring .* timeout)" "$K" 2>/dev/null; then
      echo "fault seen at $(date +%T): stopping the run's emulator"; ssh bc250 "pkill -x kyty_emulator"; break
    fi
    kill -0 $KP 2>/dev/null || break
    sleep 1
  done ) &
WP=$!
# the thread sampler (exp 0215's, read-only /proc, nice 5): waits for the run's emulator and ends with it
ssh bc250 "setsid nohup timeout 900 nice -n 5 python3 -I ~/bc5-work/exp$N/hoststate0252.py ~/bc5-work/exp$N/hs-$TAG.txt 0.1 50 < /dev/null > /dev/null 2>&1 &"
ssh bc250 "ENVX='$COMMON BC5_DIRECT_SKIP_PGM=$SKIP $POOL' SERIES=13 STEP=5 LOADWAIT=90 bash ~/bc5-work/exp$N/bench$N.sh $TAG 300" 2>&1 | tee "$D/bench-$TAG.txt"
wait $KP; kill $WP 2>/dev/null
echo "== arm $ARM ($TAG) done $(date +%T); kernel lines: $(grep -c amdgpu "$K") amdgpu of $(wc -l < "$K")"
