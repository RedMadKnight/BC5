#!/usr/bin/env bash
# BC5 exp 0439: one box-side wait (the top session's rule of 11-21: no laptop-side polling). Waits until exp 0438's
# lock line has been seen (its run goes first), then until BOX-LOCK is empty and no emulator runs on two checks 60 s
# apart; takes the lock, runs p2 (private normal a213c7f0, mode 2, map rule, 30 s), collects, releases. At most 60 min.
#   bash p2wait.sh
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator
[ "$(md5sum < "$BIN" | cut -c1-8)" = a213c7f0 ] || { echo "the binary is not a213c7f0"; exit 1; }
seen=0; free=0
for i in $(seq 1 120); do
  grep -q 'exp0438\|exp 0413\|a1j438\|0438' "$L" 2> /dev/null && seen=1
  if [ $seen = 1 ] && [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (seen 0438: $seen; lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
rm -rf runs/p2
RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/PPSA26344/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1" bash run0439.sh run normal p2 30 2>&1 | tail -1
sleep 5
for i in $(seq 1 20); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
pgrep -x kyty_emulator > /dev/null && { echo "EMULATOR STILL RUNNING: ended"; pkill -TERM -x kyty_emulator; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal p2 > /dev/null 2>&1
bash e0439.sh unlock 2>&1 | tail -1
grep -E 'binary|reset|end' runs/p2/meta.txt
grep -a 'tag dc439' runs/p2/play-last.log | grep -v 'registered compressed' | head -40 | cut -c1-500
echo ---
grep -a -v 'ports pack 1 hits' runs/p2/play-last.log | tail -n 6 | cut -c1-250
grep -i -E 'amdgpu|gpu-watch' runs/p2/kernel.txt | tail -n 8 | cut -c1-200
ls -t "$HOME/bc5-data/captures/faults" | head -1
