#!/usr/bin/env bash
# BC5 exp 0439 (tag f52), the 0x52 wake test (the top session, 11-21 ~15:40): BC5_0439_FIRE52 = 1 (once at our first
# flip), 2 (every flip), 3 (once at the first guest compute-queue job's completion); a test arm, not a fix. Private
# normal 7d7a182b (patch 0fede35d's tree), mode 2 DCC, map rule, token; 30 s each. One box-side wait for an empty lock
# (no laptop polling); reset lines before and after each run; the series stops on a fault record or a reset line.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator
[ "$(md5sum < "$BIN" | cut -c1-8)" = 6b1f9ef1 ] || { echo "the binary is not 6b1f9ef1"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep "^kyty_emulator" > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
base="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/TITLE3/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_0439_EOP_TOKEN=1 BC5_RUN_ENV=$HOME/bc5-work/exp0439/run-log.env"
faults0=$(ls "$HOME/bc5-data/captures/faults" | wc -l)
for arm in R1:1:0 R2:1:x52; do
  m=${arm#*:}; d=${m#*:}; m=${m%%:*}; tag=kw${arm%%:*}
  O=runs/$tag; rm -rf "$O"
  RUN_PRIV=$BIN RUN_EXTRA="$base BC5_0439_FIRE52=$m BC5_0439_FIRE52_DATA=$d" bash run0439.sh run normal "$tag" 30 2>&1 | tail -1
  for k in $(seq 1 60); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.1; done
  P=$(pgrep "^kyty_emulator" | head -1)
  : > "$O.labels"
  for t in 5 10 15 20 25; do
    sleep 5
    [ -n "$P" ] && kill -0 "$P" 2> /dev/null || break
    python3 -I - "$P" "$t" >> "$O.labels" 2>&1 << 'EOF'
import sys
pid, t = int(sys.argv[1]), sys.argv[2]
out = []
with open(f"/proc/{pid}/mem", "rb") as m:
    for a in (0x2000000000, 0x2000000020, 0x2000000040, 0x2010449750, 0x20104cd1e0, 0x20104aa630):
        m.seek(a); out.append(f"{a:x}={int.from_bytes(m.read(8), 'little'):x}")
print(f"t {t} s: " + " ".join(out))
EOF
    if [ "$t" = 15 ]; then
      for tk in /proc/$P/task/*; do [ "$(cat $tk/comm 2> /dev/null)" = ProxySetSync ] && echo "ProxySetSync $(basename $tk): $(awk '{print $3}' $tk/stat) wchan $(cat $tk/wchan 2> /dev/null)" >> "$O.labels"; done
    fi
  done
  for k in $(seq 1 20); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
  pgrep "^kyty_emulator" > /dev/null && { echo "m$m: EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
  RUN_PRIV=$BIN bash run0439.sh collect normal "$tag" > /dev/null 2>&1
  mkdir -p "$O"; mv "$O.labels" "$O/labels.txt" 2> /dev/null
  PL=$O/play-last.log
  r0=$(grep before "$O/meta.txt" | sed 's/.*before: //'); r1=$(grep after "$O/meta.txt" | sed 's/.*after: //')
  echo "== $arm: resets $r0 -> $r1; flips $(grep -a -c 'tag dc439): t .* flip:' $PL); f52 lines $(grep -a -c 'tag f52): t' $PL); dcb replays $(grep -a -c 'tag rp439): t .* starts' $PL) (last at $(grep -a 'tag rp439): t .* starts' $PL | tail -1 | sed -E 's/.* t ([0-9.]+) s.*/\1/'))"
  grep -a 'tag f52): t' $PL | head -5 | cut -c1-160
  cat "$O/labels.txt"
  grep -a 'tag kv439' $PL | head -14 | cut -c1-170
  n=$(ls "$HOME/bc5-data/captures/faults" | wc -l)
  if [ "$n" != "$faults0" ] || [ "$r0" != "$r1" ]; then echo "mode $m: a fault record or a reset line: the series stops"; break; fi
done
bash e0439.sh unlock 2>&1 | tail -1
