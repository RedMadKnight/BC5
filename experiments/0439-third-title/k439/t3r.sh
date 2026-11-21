#!/usr/bin/env bash
# BC5 exp 0439: run 3 for the record of the hang in queue 40's chained continuation (the top session's GO, 11-21 ~20:10): the
# guard build (its md5 as the first argument), the 17:04 settings (BC5_DIRECT_JOURNAL=min), the timeout probe, plus
# BC5_0439_PIECE_DUMP=1 (every chained/called piece of the timed-out job), BC5_DIRECT_UMR_ON_TIMEOUT=1 + BC5_0439_UMR_WAVES=1
# (umr -O halt_waves -wa none at the 0.9-s watchdog), BC5_0439_XQ_COUNT=1 (the ring map), and BC5_0439_IMPORT_PIECES=$2
# (0 or 1), and BC5_DIRECT_IB_CHAIN_FLAT=1 (a compute job's chain laid out flat; the top session's decision, 20:40: both fix
# candidates in one run, to spare reboots). R72 gates measurements only: a diagnosis run, the display line recorded. 120 s bound inside the container.
# Start at a clock time (R73: the box-side wait inside this script), so the maintainer can watch; screenshots of the output
# (spectacle, the session's Wayland and D-Bus) at about 4, 8 and 11 s after the emulator's start and then every 15 s while
# it runs, into ~/bc5-data/priv/yotei-screens/<tag>/ (mode 700): private, never in git, never attached to a report.
#   t3r.sh <md5-8> <import 0|1> [HH:MM:SS start]
# One box-side wait for a free lock and no emulator (30 min at most, R64), then the run.
# Before: the R72 display line, the dead-mount check, resets and fault records. During: the kernel log streamed to a file
# with its own timeout (R64, R67). The lock only for the run. Output under runs/t3r-i<import>/.
set -u
cd "$HOME/bc5-work/exp0439" || exit 1
PIN=${1:?md5}; IMP=${2:?import 0 or 1}; START=${3:-}; case "$IMP" in 0|1) ;; *) echo "import is 0 or 1"; exit 1 ;; esac
L=$HOME/bc5-work/BOX-LOCK; BIN=$HOME/bc5-work/exp0439/k439/normal/kyty_emulator; O=runs/t3r-i$IMP
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || { echo "the binary is not $PIN"; exit 1; }
for w in BC5_0439_PIECE_DUMP BC5_0439_UMR_WAVES BC5_0439_IMPORT_PIECES BC5_0439_XQ_COUNT BC5_DIRECT_IB_CHAIN_FLAT; do grep -aq $w "$BIN" || { echo "no $w in the binary"; exit 1; }; done
EXTRA="BC5_SYSMODULES_PACK_DIR=$HOME/bc5-data/games/PPSA26344/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_0439_PIECE_DUMP=1 BC5_DIRECT_UMR_ON_TIMEOUT=1 BC5_0439_UMR_WAVES=1 BC5_0439_XQ_COUNT=1 BC5_0439_IMPORT_PIECES=$IMP BC5_DIRECT_IB_CHAIN_FLAT=1"
if [ "${DRY:-0}" = 1 ]; then # the launch as it would go, nothing started, no lock (R66)
  echo "DRY: binary $PIN ok, switches present; start ${START:-now}; run0439.sh run normal t3r-i$IMP 120 with RUN_PRIV=$BIN"
  echo "DRY: RUN_EXTRA=$EXTRA"
  grep -q '^BC5_DIRECT_JOURNAL=min$' "$HOME/bc5-work/bc5-run.env" && echo "DRY: bc5-run.env sets BC5_DIRECT_JOURNAL=min"
  grep -n 'P439_BIN\|exec\|"\$EMU"' "$HOME/bc5-work/exp0439/k439/play439.sh" | head -4
  bash "$HOME/bc5-work/exp0439/k439/r72check.sh"
  exit 0
fi
free=0
for i in $(seq 1 120); do
  if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null; then free=$((free + 1)); else free=0; fi
  [ $free -ge 2 ] && break
  sleep 15
done
[ $free -ge 2 ] || { echo "$(date +%T) no free box after 30 min (lock [$(cat "$L")])"; exit 1; }
grep -q '^BC5_DIRECT_JOURNAL=min$' "$HOME/bc5-work/bc5-run.env" || { echo "bc5-run.env does not set BC5_DIRECT_JOURNAL=min"; exit 1; }
rm -rf "$O"; mkdir -p "$O"
if ! bash k439/r72check.sh | tee "$O/display.txt"; then
  # LESSONS R72 as extended 11-21 20:14: once, then check again (never during a measured run; this is a diagnosis run)
  echo "display check failed: sudo -n /usr/local/bin/bc5-display-redetect --if-needed" | tee -a "$O/display.txt"
  sudo -n /usr/local/bin/bc5-display-redetect --if-needed 2>&1 | tail -3 | tee -a "$O/display.txt"
  sleep 3
  bash k439/r72check.sh | tee -a "$O/display.txt" || echo "  (still bad: a diagnosis run goes on, the mode recorded)"
fi
journalctl -b -u bc5-display-redetect --no-pager 2> /dev/null | tail -2 | tee -a "$O/display.txt"
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
if [ -n "$START" ]; then # R73: wait on the box until the given clock time (at most 30 min)
  tgt=$(date -d "$START" +%s 2> /dev/null) || { echo "bad start time $START"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
  now=$(date +%s); [ $((tgt - now)) -gt 1800 ] && { echo "start time over 30 min away"; bash e0439.sh unlock 2>&1 | tail -1; exit 1; }
  [ "$tgt" -gt "$now" ] && sleep $((tgt - now))
  echo "$(date +%T) starting (asked for $START)"
fi
SH=$HOME/bc5-data/priv/yotei-screens/t3r-i$IMP-$(date +%H%M); mkdir -p "$SH" && chmod 700 "$HOME/bc5-data/priv/yotei-screens" "$SH"
shot() { XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$(ls -1 /run/user/$(id -u)/ | grep -m1 -E '^wayland-[0-9]+$') DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus   timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1 && echo "$1" >> "$SH/shots.txt"; }
( for k in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null && break; sleep 0.5; done
  t0=$(date +%s); for at in 4 8 11; do sleep $((t0 + at - $(date +%s))); shot "t$(printf %03d $at)s"; done
  at=26; while pgrep -x kyty_emulator > /dev/null && [ $at -le 135 ]; do sleep $((t0 + at - $(date +%s))) 2> /dev/null; shot "t$(printf %03d $at)s"; at=$((at + 15)); done
  shot "after" ) &
SHP=$!
RUN_PRIV=$BIN RUN_EXTRA="$EXTRA" bash run0439.sh run normal t3r-i$IMP 120 2>&1 | tail -1
sleep 5; for k in $(seq 1 40); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
pgrep -x kyty_emulator > /dev/null && { echo "EMULATOR STILL RUNNING: ended"; pkill -TERM -x kyty_emulator; sleep 5; }
RUN_PRIV=$BIN bash run0439.sh collect normal t3r-i$IMP > /dev/null 2>&1
kill $KJ 2> /dev/null
wait $SHP 2> /dev/null
echo "screenshots: $(ls "$SH" | grep -c png) in $SH"
PL=$O/play-last.log
grep -a "frame profile" "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null | tail -2 | cut -c1-200
echo "r438 BUG lines: $(grep -a -c 'r438 (exp 0438, b438): BUG' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null)"
grep -a -c "tag ip439" $O/play-last.log 2> /dev/null | sed 's/^/ip439 lines: /'
echo "fl439: flattened $(grep -a -c 'tag fl439): .* laid out flat:' $O/play-last.log), refused $(grep -a -c 'tag fl439): .* NOT laid out flat' $O/play-last.log); k1f412 imports $(grep -a -c 'k1 at the filter' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null), ud434 imports $(grep -a -c 'user-data target (exp 0434' "$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log" 2> /dev/null)"
grep -a 'tag fl439\|tag ip439\|tag pd439' $O/play-last.log | head -6 | cut -c1-220
echo "== t3r-i$IMP: $(grep before $O/meta.txt | sed 's/.*before: /resets /') -> $(grep after $O/meta.txt | sed 's/.*after: //'); fault records $(ls ~/bc5-data/captures/faults | wc -l); flips $(grep -a -c 'tag dc439): t .* flip:' $PL); decompress OK $(grep -a -c 'decompress of index .*: OK' $PL); exit $(grep -a '== .* exit' $PL | tail -1 | sed 's/.* exit //')"
grep -a 'GPU FAULT\|Error ---' -A2 $PL | head -6 | cut -c1-220
grep -a -i 'amdgpu' "$O/klog.txt" | head -8 | cut -c1-200
ls -d ~/bc5-data/captures/play-* | tail -1
bash e0439.sh unlock 2>&1 | tail -1
