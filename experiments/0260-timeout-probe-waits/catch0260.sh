#!/usr/bin/env bash
# BC5 experiment 0260: the catch run, scripted (the box supervisor's choice, 2026-10-24). Exp 0254's run0254b.sh (the
# APR session's) cut down to its title pkgn: the second title, the normal launcher with its defaults (play-pkg.sh: the
# held tail, the CS prefix, the tiler pool, the probe), S6N's route (exp 0203's o2-continue.cmd from exp 0196's
# saves-before-152617, put in and taken back by exp 0196's ab-restore.sh, which refuses a copy that is not its own).
# Two changes:
#   - BC5_EMU = ~/bc5-work/exp0260/kyty_emulator (patch0260.py's probe), BC5_DIRECT_TIMEOUT_PROBE=1 set explicitly; the
#     md5 of the emulator's /proc/<pid>/exe is checked against it;
#   - the route repeated: up to RUNS runs of SECS each (default 4 x 300 s), each with its own save restore. The chain
#     stops after the first run that is not a pass: a new kernel amdgpu line (checked every 5 s; the run is stopped at
#     once), a TIMEOUT in its journal, a crash line, or saves that did not come back.
# The live saves' checksum (exp 0253's method: the md5 of the sorted per-file md5s of PPSA03671) must be
# 1a39860996fdac5c before the chain and after it. Only the emulator PID a run started is ever stopped.
# Attended: on the box supervisor's GO, with the maintainer reachable for a power-cycle and stream0260.sh running on the
# laptop. After a machine-down the live saves are in exp0196/saves-before-* (the run's KEEP, named in <tag>-restore.txt):
# put them back by hand with ab-restore.sh <KEEP> and check the checksum.
# usage: catch0260.sh [runs] [secs]   (on the box)
set -u
RUNS=${1:-4}; SECS=${2:-300}
E=$HOME/bc5-work/exp0260; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$E/kyty_emulator; WANT=9c55e29e
# The live saves' checksum: 1a39860996fdac5c for the run of 2026-10-24 14:49; db52cb5f327c3de5 since 15:19, when 17 stray
# 3-byte .blocks sidecars (F319) were moved out of the save folders (~/bc5-work/exp0258/stray-blocks-backup-151948).
WANT_SAVES=db52cb5f327c3de5
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-last.log
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH" ] && [ -x "$W/exp0196/ab-restore.sh" ] || { echo "no $SAVES, $LAUNCH or ab-restore.sh"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
S0=$(saves); echo "$(date '+%F %T') live saves $S0 (want $WANT_SAVES)" | tee -a "$R/catch-saves.txt"
[ "$S0" = "$WANT_SAVES" ] || { echo "the live saves are not $WANT_SAVES: not started"; exit 1; }
echo "exp 0260 | catch run: the second title's S6N route, up to $RUNS x $SECS s, exp0260 binary (timeout probe), maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0260 | catch run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass or FAIL: ... last
  local TAG=$1 OUT KEEP N EP T0 ENDED="" J NK NC NT FAIL=""
  [ -e "$R/$TAG-start.txt" ] && { echo "FAIL: tag $TAG already used"; return; }
  sleep 2  # ab-restore.sh names its copies by time
  OUT=$("$W/exp0196/ab-restore.sh" "$SAVES") || { echo "FAIL: route saves not put in: $OUT"; return; }
  echo "$OUT" > "$R/$TAG-restore.txt"
  KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
  [ -d "$KEEP" ] || { echo "FAIL: the live saves were not kept"; return; }
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  N=$(sudo -n dmesg 2> /dev/null | wc -l)
  { date '+%F %T'; echo "run $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT"
    echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; boxstate start; } > "$R/$TAG-start.txt"
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_HOLD_TAIL|BC5_DIRECT_CS_PREFIX|BC5_DIRECT_CHAIN|BC5_DIRECT_COMPUTE_RING|BC5_DIRECT_CROSS_RING_WAITS|BC5_DIRECT_RING_ORDER_WAITS|KYTY_BC5_TILER_POOL|PLAY_CAPTURE|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"  # by content: /home is /var/home on the box
  fi
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu" && { ENDED="kernel amdgpu line at $(($(date +%s) - T0)) s"; break; }
    sleep 5
  done
  boxstate end > "$R/$TAG-box-end.txt"
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  sleep 3
  echo "$TAG ${ENDED:-stopped at $SECS s}" > "$R/$TAG-end.txt"
  cp -p "$LOG" "$R/$TAG-play.log" 2> /dev/null
  grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt" 2> /dev/null
  J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J")"
      [ -f "$W/exp0254/jcount0254.awk" ] && nice -n 19 awk -f "$W/exp0254/jcount0254.awk" "$J"; } > "$R/$TAG-journal.txt"
    nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  sleep 2
  "$W/exp0196/ab-restore.sh" "$KEEP" > "$R/$TAG-restore-back.txt" 2>&1
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then echo "NESTED SAVE COPY in $KEEP or $SD" >> "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" >> "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" >> "$R/$TAG-restore-back.txt"; fi
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG: ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, probe lines $(grep -c "timeout probe" "$R/$TAG-probe.txt")" > "$R/$TAG-summary.txt"
  case "$ENDED" in "" ) ;; *) FAIL="$FAIL $ENDED;" ;; esac
  [ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
  [ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
  [ "$NT" = 0 ] || FAIL="$FAIL $NT TIMEOUT lines;"
  grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
  if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi > "$R/$TAG-verdict.txt"
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for i in $(seq 1 "$RUNS"); do
  TAG=K$i
  echo "== $(date +%T) run $TAG"
  one "$TAG"
  grep -q "^pass" "$R/$TAG-verdict.txt" 2> /dev/null || { echo "== $(date +%T) the chain stops after $TAG"; break; }
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/catch-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES: put them back by hand"
grep -q "^exp 0260 | catch run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
