#!/usr/bin/env bash
# BC5 experiment 0294: S6N runs with one private binary that carries exp 0290's compute-ring refusal (backend archive
# 825ae1d1) and exp 0277's breadcrumbs (exp 0281's bc5LleAgc.cpp.o), RT on, BC5_DIRECT_BREADCRUMBS=1. Exp 0290's s6n0290.sh
# (exp 0265's chain) with the breadcrumb extracts of exp 0281's catch0281.sh: per run the health lines and the probe's
# "breadcrumbs (exp 0277)" lines (<tag>-crumbs.txt), which at a recovered hang name the first dispatch reached and not
# done. The recovered-hang rule of 0290 S2-S6 (a GFX-ring hang the kernel recovers from is a pass; the host's 2-s fence
# timeout is part of it); the chain stops on a failed reset, MODE1, a crash or saves not back. Up to RUNS x SECS
# (default 4 x 600 s), each run with its own save restore; the live saves must be the supervisor's reference.
# The live saves (PPSA03671) are snapshot at chain start into exp0294/saves-before-<HHMM>; their checksum then (exp 0253's
# method) must hold after every run's restore and at the end, and the chain stops when it does not. No value is
# hard-coded: the maintainer plays and saves between runs (2026-10-24: 16:04, 16:10, 16:46, 16:55).
# Only the emulator PID a run started is ever stopped. Attended: on the box supervisor's GO and the maintainer's approval
# in the tcp session, with him reachable for a power-cycle and stream0265.sh on the laptop. After a machine-down the live
# saves are in the run's exp0196/saves-before-* (named in <tag>-restore.txt) and in the chain's snapshot: put them back by
# hand with ab-restore.sh <KEEP> and check the checksum against s6n-saves.txt.
# usage: count0265.sh [runs] [secs]   (on the box)
set -u
RUNS=${1:-4}; SECS=${2:-600}; FIRST=${3:-1}   # FIRST: the first run number (S2 after a chain that ended at S1)
E=$HOME/bc5-work/exp0294; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2>/dev/null)   # written by build0290.sh
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-last.log
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH" ] && [ -x "$W/exp0196/ab-restore.sh" ] || { echo "no $SAVES, $LAUNCH or ab-restore.sh"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP" | tee -a "$R/s6n-saves.txt"
echo "exp 0294 | s6n run: the second title's S6N route, up to $RUNS x $SECS s, exp0294 binary (the refusal + exp 0277.s breadcrumbs, BC5_DIRECT_BREADCRUMBS=1), maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0294 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass or FAIL: ... last
  local TAG=$1 OUT KEEP N EP T0 ENDED="" J NK NC NT FAIL="" RECOVERED=""
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
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_BREADCRUMBS=1 KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_RING_ORDER_STALE|BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_HOLD_TAIL|BC5_DIRECT_CS_PREFIX|BC5_DIRECT_CHAIN|BC5_DIRECT_COMPUTE_RING|BC5_DIRECT_CROSS_RING_WAITS|BC5_DIRECT_RING_ORDER_WAITS|KYTY_BC5_TILER_POOL|PLAY_CAPTURE|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"  # by content: /home is /var/home on the box
  fi
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
      ENDED="kernel amdgpu line at $(($(date +%s) - T0)) s"
      # exp 0294 (the supervisor.s rule for S2-S6): a GFX-ring hang the kernel recovers from (ring reset succeeded, no
      # failed reset, no MODE1) counts as a pass for the question "does the box stay up"; wait for the kernel.s verdict.
      sleep 25
      if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded" && ! sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "reset failed|MODE1|GPU reset begin|mode1"; then
        ENDED="recovered GFX-ring hang: $ENDED, ring reset succeeded"; RECOVERED=1
      fi
      break
    fi
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
    nice -n 19 grep -a "^ring order: STALE" "$J" > "$R/$TAG-stale.txt"
    nice -n 19 grep -a "breadcrumbs (exp 0277)" "$J" > "$R/$TAG-crumbs.txt"   # exp 0294: the health lines and the probe.s breadcrumb lines
    sed -n 's/^ring order: STALE pending write on \(0x[0-9a-f]*\).*/\1/p' "$R/$TAG-stale.txt" | sort | uniq -c | sort -rn > "$R/$TAG-stale-labels.txt"
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-crumbs.txt"; : > "$R/$TAG-stale.txt"; : > "$R/$TAG-stale-labels.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  # the maintainer's devcoredump copies since 2026-10-24 17:15 (CLAUDE.md): paths and sizes only, the dumps are never copied out
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  sleep 2
  "$W/exp0196/ab-restore.sh" "$KEEP" > "$R/$TAG-restore-back.txt" 2>&1
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then echo "NESTED SAVE COPY in $KEEP or $SD" >> "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" >> "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" >> "$R/$TAG-restore-back.txt"; fi
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG: ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, probe lines $(grep -c "timeout probe" "$R/$TAG-probe.txt"), devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), breadcrumb lines $(grep -c . "$R/$TAG-crumbs.txt"), STALE lines $(grep -c . "$R/$TAG-stale.txt"); last: $(tail -1 "$R/$TAG-stale.txt" | sed 's/.*(\([0-9]* stale of [0-9]* checked\)).*/\1/')" > "$R/$TAG-summary.txt"
  case "$ENDED" in "" | recovered*) ;; *) FAIL="$FAIL $ENDED;" ;; esac
  [ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
  [ "$NK" = 0 ] || [ -n "$RECOVERED" ] || FAIL="$FAIL $NK kernel lines (recovered hangs are passes);"
  [ "$NT" = 0 ] || [ -n "$RECOVERED" ] || FAIL="$FAIL $NT TIMEOUT lines;"   # exp 0294: the host.s 2-s fence timeout is part of a recovered hang
  grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
  if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi > "$R/$TAG-verdict.txt"
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for i in $(seq "$FIRST" $((FIRST + RUNS - 1))); do
  TAG=S$i
  echo "== $(date +%T) run $TAG"
  one "$TAG"
  SN=$(saves); echo "$(date '+%F %T') after $TAG live saves $SN (want $WANT_SAVES)" >> "$R/s6n-saves.txt"
  [ "$SN" = "$WANT_SAVES" ] || { echo "== $(date +%T) the live saves are not $WANT_SAVES after $TAG: the chain stops (snapshot $SNAP)"; break; }
  grep -q "^pass" "$R/$TAG-verdict.txt" 2> /dev/null || { echo "== $(date +%T) the chain stops after $TAG"; break; }
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES: put them back by hand from $SNAP"
grep -q "^exp 0294 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
