#!/usr/bin/env bash
# BC5 exp 0439: run 2 for the record of the hang at about frame 230 (the top session's GO, 11-21 ~20:05). t3p's full journal
# slowed every frame to 1.1 s; this is the 17:04 condition exactly (private normal 3a79a88e, the 17:04 settings,
# BC5_DIRECT_JOURNAL=min from bc5-run.env) plus only BC5_DIRECT_TIMEOUT_PROBE=1. 120 s bound inside the container.
# One box-side wait for a free lock and no emulator (30 min at most, R64), then the run.
# Before: the R72 display line, the dead-mount check, resets and fault records. During: the kernel log streamed to a file
# with its own timeout (R64, R67). The lock only for the run. Output under runs/t3q/.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator; O=runs/t3q
[ "$(md5sum < "$BIN" | cut -c1-8)" = 3a79a88e ] || { echo "the binary is not 3a79a88e"; exit 1; }
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 15
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box after 30 min (lock [$(cat "$L")])"; exit 1; }
grep -q '^BC5_DIRECT_JOURNAL=min$' "$HOME/bc5-work/bc5-run.env" || { echo "bc5-run.env does not set BC5_DIRECT_JOURNAL=min"; exit 1; }
rm -rf "$O"; mkdir -p "$O"
bash k439/r72check.sh | tee "$O/display.txt"
for where in container host; do
  if [ $where = container ]; then run_in() { distrobox enter ubuntu -- bash -c "$1"; }; else run_in() { bash -c "$1"; }; fi
  run_in 'for d in "$HOME"/bc5-data/mnt/*; do [ -d "$d" ] || continue; if mountpoint -q "$d" && ! [ -s "$d/sce_sys/param.json" ]; then echo "dead mount $d: unmounted"; fusermount3 -u "$d" 2>&1 || fusermount3 -u -z "$d" 2>&1; fi; done' 2>&1 | sed "s/^/$where: /"
done
bash e0439.sh lock 2>&1 | tail -1
grep -q '^exp0439 ' "$L" || { echo "lock not taken: [$(cat "$L")]"; exit 1; }
echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); resets $(journalctl -k -b 0 --no-pager | grep -c -i -E 'amdgpu.*(timeout|reset)'); fault records $(ls ~/bc5-data/captures/faults | wc -l)" | tee "$O/before.txt"
timeout 220 journalctl -k -f -n 0 --no-pager > "$O/klog.txt" 2>&1 &
KJ=$!
: > "$HOME/bc5-work/play-last.log"
RUN_PRIV=$BIN RUN_EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/PPSA26344/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_TIMEOUT_PROBE=1" bash run0439.sh run normal t3q 120 2>&1 | tail -1
sleep 5; for k in $(seq 1 40); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
pgrep -x kyty_emulator > /dev/null && { echo "EMULATOR STILL RUNNING: ended"; pkill -TERM -x kyty_emulator; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal t3q > /dev/null 2>&1
kill $KJ 2> /dev/null
PL=$O/play-last.log
grep -a "frame profile" "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null | tail -2 | cut -c1-200
echo "r438 BUG lines: $(grep -a -c 'r438 (exp 0438, b438): BUG' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null)"
echo "== t3q: $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); fault records $(ls ~/bc5-data/captures/faults | wc -l); flips $(grep -a -c 'tag dc439): t .* flip:' $PL); decompress OK $(grep -a -c 'decompress of index .*: OK' $PL); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
grep -a 'GPU FAULT\|Error ---' -A2 $PL | head -6 | cut -c1-220
grep -a -i 'amdgpu' "$O/klog.txt" | head -8 | cut -c1-200
ls -d ~/bc5-data/captures/play-* | tail -1
bash e0439.sh unlock 2>&1 | tail -1
