#!/usr/bin/env bash
# BC5 exp 0439, problem 3 (the stall after the first flip): one 25-s run as a0 (private normal a213c7f0, mode 2, map
# rule) with a sampler at about 14 s: every thread's name, state and CPU ticks over 1 s (who spins), the values at the
# waited-on labels (read through /proc/<pid>/mem; ptrace_scope 0 on the box), and eu-stack of the four busiest threads
# (their frame 0 shows what guest code runs). One box-side wait for an empty lock, as arms3.sh. Output under runs/a3/.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator; O=runs/a13
[ "$(md5sum < "$BIN" | cut -c1-8)" = fb55ba6f ] || { echo "the binary is not fb55ba6f"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep "^kyty_emulator" > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 30
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box (lock [$(cat "$L")])"; exit 1; }
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
rm -rf "$O"
RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/TITLE3/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1" bash run0439.sh run normal a13 25 2>&1 | tail -1
for k in $(seq 1 30); do pgrep "^kyty_emulator" > /dev/null && break; sleep 0.5; done
P=$(pgrep "^kyty_emulator" | head -1)
sleep 14
if [ -n "$P" ] && kill -0 "$P" 2> /dev/null; then
  ticks() { for t in /proc/$P/task/*; do echo "$(basename $t) $(awk '{print $14+$15, $3}' $t/stat 2> /dev/null) $(cat $t/comm 2> /dev/null)"; done; }
  ticks > "$O/t0.txt"; sleep 1; ticks > "$O/t1.txt"
  join <(sort "$O/t0.txt") <(sort "$O/t1.txt") | awk '{d=$5-$2; print d, $1, $6, $7}' | sort -rn > "$O/threads.txt"
  head -n 12 "$O/threads.txt"
  python3 -I - "$P" > "$O/labels.txt" 2>&1 <<'EOF'
import sys
pid = int(sys.argv[1])
with open(f"/proc/{pid}/mem", "rb") as m:
    for a in (0x2010449750, 0x20104aa630, 0x20104cd100, 0x20104cd140, 0x20104cd180, 0x20104cd1c0, 0x20104cd1e0, 0x20000081e0):
        try:
            m.seek(a); v = m.read(8); print(f"0x{a:x}: {int.from_bytes(v, 'little'):#018x}")
        except OSError as e:
            print(f"0x{a:x}: {e}")
EOF
  cat "$O/labels.txt"
  distrobox enter ubuntu -- eu-stack -p "$P" -n 12 > "$O/all-stacks.txt" 2>&1
  for tid in $(head -n 4 "$O/threads.txt" | awk '{print $2}'); do
    echo "== tid $tid $(cat /proc/$P/task/$tid/comm 2> /dev/null)"
    awk -v t="$tid" '$1=="TID" {on=($2==t":"||$2==t)} on' "$O/all-stacks.txt" | head -n 14
  done > "$O/stacks.txt" 2>&1
  cat "$O/stacks.txt" | cut -c1-160
fi
for k in $(seq 1 20); do pgrep "^kyty_emulator" > /dev/null || break; sleep 5; done
pgrep "^kyty_emulator" > /dev/null && { echo "EMULATOR STILL RUNNING: ended"; pkill -TERM "^kyty_emulator"; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal a13 > /dev/null 2>&1
echo "resets: $(grep before $O/meta.txt | sed 's/.*before: //') -> $(grep after $O/meta.txt | sed 's/.*after: //')"
bash e0439.sh unlock 2>&1 | tail -1
