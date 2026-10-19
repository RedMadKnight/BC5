#!/usr/bin/env bash
# BC5 exp 0165: build the emulator (host + backend edits of ADR 0010 A/B), then runs 801, 802, 803 one after another (200 s each, drive0163.sh).
cd ~/bc5-work; exec > ~/bc5-work/seq0165.log 2>&1
echo "exp0165 (chain session): building kyty_emulator $(date +%T)" >> box-claims.txt
if pgrep -x kyty_emulator >/dev/null; then echo "emulator running, abort"; exit 1; fi
distrobox enter ubuntu -- cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8 > ~/bc5-work/build-0165.log 2>&1 || { echo "build failed"; echo "exp0165: build FAILED $(date +%T)" >> box-claims.txt; exit 1; }
ls -la --time-style=+%H:%M:%S ~/bc5-work/kytyplus-build/src/kyty_emulator
for N in 801 802 803; do
  if pgrep -x kyty_emulator >/dev/null; then echo "emulator running before run $N, abort"; exit 1; fi
  echo "exp0165 run $N started $(date +%T) by the chain session ($(grep -o "BC5_DIRECT_CHAIN=[0-9]" run$N.sh || echo chain off))" >> box-claims.txt
  setsid nohup ./drive0163.sh $N > /dev/null 2>&1 &
  sleep 2
  setsid nohup distrobox enter ubuntu -- ~/bc5-work/run$N.sh > /dev/null 2>&1 &
  for i in $(seq 1 300); do grep -q DONE drive$N.log 2>/dev/null && break; sleep 1; done
  echo "run $N: $(tail -2 drive$N.log | tr "\n" " ") at $(date +%T)"
  for i in $(seq 1 30); do pgrep -x kyty_emulator >/dev/null || break; sleep 1; done
  sleep 10
done
echo "exp0165: runs done $(date +%T)" >> box-claims.txt
echo ALLDONE
