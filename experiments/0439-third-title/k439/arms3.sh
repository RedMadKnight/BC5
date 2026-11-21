#!/usr/bin/env bash
# BC5 exp 0439: problem 3's env-only arms (the top session, 11-21 ~13:05), one box-side wait (no laptop polling).
# Waits until BOX-LOCK is empty and no emulator runs on two checks 30 s apart (at most 60 min), takes the lock, and runs
# on the private normal a213c7f0 (mode 2, map rule), 30 s each, with KytyPlus's guest log on (run-log.env:
# PLAY_ARGS=--printf-direction Console, for the VideoOut calls after the first flip):
#   a0: as p2;  a1: + BC5_DIRECT_ACB_RINGS=0;  a2: + BC5_0438_EARLYREG=0
# Reset lines before and after each; stops the series on a fault record or a reset line. Releases the lock.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator
[ "$(md5sum < "$BIN" | cut -c1-8)" = a213c7f0 ] || { echo "the binary is not a213c7f0"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
base="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/PPSA26344/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_RUN_ENV=$HOME/bc5-work/exp0439/run-log.env"
faults0=$(ls "$HOME/bc5-data/captures/faults" | wc -l)
for arm in a0 a1 a2; do
  extra=$base
  [ $arm = a1 ] && extra="$base BC5_DIRECT_ACB_RINGS=0"
  [ $arm = a2 ] && extra="$base BC5_0438_EARLYREG=0"
  rm -rf "runs/$arm"
  RUN_PRIV=$BIN RUN_EXTRA="$extra" bash run0439.sh run normal "$arm" 30 2>&1 | tail -1
  sleep 5
  for k in $(seq 1 20); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
  pgrep -x kyty_emulator > /dev/null && { echo "$arm: EMULATOR STILL RUNNING: ended"; pkill -TERM -x kyty_emulator; sleep 5; }
  RUN_PRIV=$BIN bash run0439.sh collect normal "$arm" > /dev/null 2>&1
  echo "== $arm: $(grep -E 'before' runs/$arm/meta.txt | sed 's/.*before: //') -> $(grep -E 'after' runs/$arm/meta.txt | sed 's/.*after: //') reset lines; extra: ${extra#$base}"
  grep -a -c 'tag dc439): t .* flip:' "runs/$arm/play-last.log" | sed 's/^/   flips: /'
  grep -a 'tag dc439): t .* \(presented\|keys:\|decompress\)' "runs/$arm/play-last.log" | head -6 | cut -c1-200
  grep -a -E '\[bc5-q\].*deferred|cpu-wait .*TIMEOUT' "$(sed -n 's/^capture //p' runs/$arm/meta.txt)/gc/direct.log" 2> /dev/null | tail -3 | cut -c1-200
  grep -a -v 'ports pack 1 hits' "runs/$arm/play-last.log" | grep -a -E 'exit|Error|FAULT' | tail -2 | cut -c1-200
  n=$(ls "$HOME/bc5-data/captures/faults" | wc -l)
  r0=$(grep -E 'before' runs/$arm/meta.txt | sed 's/.*before: //'); r1=$(grep -E 'after' runs/$arm/meta.txt | sed 's/.*after: //')
  if [ "$n" != "$faults0" ] || [ "$r0" != "$r1" ]; then echo "$arm: a fault record or a reset line: the series stops"; break; fi
done
bash e0439.sh unlock 2>&1 | tail -1
