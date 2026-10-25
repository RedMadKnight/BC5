#!/usr/bin/env bash
# BC5 experiment 0281: RT-off runs with breadcrumbs. Exp 0265's count0265.sh (exp 0260's catch0260.sh, itself exp 0254's
# run0254b.sh for the second title) with exp 0281's private binary (md5 0a74c602): the shared normal 7947154c (exp 0278's
# switch integrated, the launchers' ten-program build list) plus exp 0277's breadcrumbs. The run environment adds
# KYTY_BC5_RT=0 and BC5_DIRECT_BREADCRUMBS=1 (level 1: a reached and a done mark around every dispatch).
#   check        one run of 180 s: the first time the breadcrumbs run on the GPU. Its health lines ("breadcrumbs (exp
#                0277): … reached and … done") show whether both marks are written; pass/fail as for a chain run.
#   chain [N S]  up to N runs of S s each (default and maximum 6 x 600 s); the chain stops after the first run that is not
#                a pass (a machine-down overnight leaves the box down until the maintainer is back).
# Every run: the second title, the normal launcher with its defaults, S6N's route (exp 0203's o2-continue.cmd from exp
# 0196's saves-before-152617 through ab-restore.sh), its own save restore. A run is stopped at the first new kernel
# amdgpu line. Per run the breadcrumbs' health lines and the probe's breadcrumb lines (<tag>-crumbs.txt), and whether RT
# was off (the build list's "ray tracing off" drop lines; the title's saved RayTracing.<TITLE_ID> overrides KYTY_BC5_RT).
# The live saves (PPSA03671) must be the box supervisor's reference (SAVES_REF) at the start; they are snapshot into
# exp0281/saves-before-<HHMM>; their checksum (exp 0253's method) must hold after every run's restore and at the end, and
# the chain stops when it does not. Each run's files are synced to the disk before the next run starts.
# Only the emulator PID a run started is ever stopped. Attended or supervised: on the box supervisor's GO and the
# maintainer's approval in the tcp session, with stream0281.sh on the laptop. After a machine-down the live saves are in
# the run's exp0196/saves-before-* (named in <tag>-restore.txt) and in the chain's snapshot: put them back by hand with
# ab-restore.sh <KEEP> and check the checksum against catch-saves.txt.
# usage: catch0281.sh check | chain [runs] [secs]   (on the box)
set -u
case "${1:-}" in
check) RUNS=1; SECS=180; PFX=C ;;
chain) RUNS=${2:-6}; SECS=${3:-600}; PFX=S ;;
*) echo "usage: catch0281.sh check | chain [runs] [secs]"; exit 2 ;;
esac
E=$HOME/bc5-work/exp0281; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$E/kyty_emulator; WANT=0a74c602; SAVES_REF=c0ee58b92c0cadc2
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-last.log
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH" ] && [ -x "$W/exp0196/ab-restore.sh" ] && [ -f "$W/exp0203/o2-continue.cmd" ] || { echo "no $SAVES, $LAUNCH, ab-restore.sh or o2-continue.cmd"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
WANT_SAVES=$(saves)
[ "$WANT_SAVES" = "$SAVES_REF" ] || { echo "the live saves are $WANT_SAVES, not the reference $SAVES_REF: not started"; exit 1; }
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
echo "$(date '+%F %T') $1: live saves $WANT_SAVES, snapshot $SNAP" | tee -a "$R/catch-saves.txt"
echo "exp 0281 | $1: the second title's S6N route, RT off with breadcrumbs, up to $RUNS x $SECS s, exp0281 binary | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0281 | " "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
EP=""; KEEP=""  # the running emulator and the kept live saves of the current run, for the handler below
# A dropped ssh session or a stop: end only this run's emulator, put the live saves back, then exit (the EXIT trap
# releases the lock), so nothing is left running unattended with the route's saves in place.
abort() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$KEEP" ] && [ -d "$KEEP" ] && "$W/exp0196/ab-restore.sh" "$KEEP" >> "$R/aborted-restore.txt" 2>&1
  echo "$(date '+%F %T') aborted; live saves $(saves) (want $WANT_SAVES)" >> "$R/catch-saves.txt"
  sync
  exit 1
}
trap abort HUP INT TERM
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass or FAIL: ... last
  local TAG=$1 OUT N T0 ENDED="" J NK NC NT NRT FAIL=""
  EP=""; KEEP=""
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
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 KYTY_BC5_RT=0 BC5_DIRECT_BREADCRUMBS=1 KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|BC5_DIRECT_BREADCRUMBS|BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_MEC_INDIRECT|BC5_DIRECT_GPU_CHECK|BC5_DIRECT_SKIP_PGM|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
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
  NRT=0
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J")"
      [ -f "$W/exp0254/jcount0254.awk" ] && nice -n 19 awk -f "$W/exp0254/jcount0254.awk" "$J"; } > "$R/$TAG-journal.txt"
    nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
    nice -n 19 grep -a "breadcrumbs (exp 0277)" "$J" > "$R/$TAG-crumbs.txt"
    NRT=$(nice -n 19 grep -a -c "ray tracing off:" "$J")
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-crumbs.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  # the maintainer's devcoredump copies (CLAUDE.md): paths and sizes only, the dumps are never copied out
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  sleep 2
  "$W/exp0196/ab-restore.sh" "$KEEP" > "$R/$TAG-restore-back.txt" 2>&1
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then echo "NESTED SAVE COPY in $KEEP or $SD" >> "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" >> "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" >> "$R/$TAG-restore-back.txt"; fi
  EP=""; KEEP=""  # the run is over and its saves are back: the handler has nothing left to undo
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG: ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, probe lines $(grep -c "timeout probe" "$R/$TAG-probe.txt"), devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), breadcrumb lines $(grep -c . "$R/$TAG-crumbs.txt"), RT-off drop lines $NRT; last health: $(grep -a "inserted" "$R/$TAG-crumbs.txt" | tail -1 | sed 's/.*(exp 0277): //')" > "$R/$TAG-summary.txt"
  case "$ENDED" in "" ) ;; *) FAIL="$FAIL $ENDED;" ;; esac
  [ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
  [ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
  [ "$NT" = 0 ] || FAIL="$FAIL $NT TIMEOUT lines;"
  [ "$NRT" -gt 0 ] || FAIL="$FAIL RT WAS NOT OFF (no drop lines);"
  grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
  if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi > "$R/$TAG-verdict.txt"
  sync
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for i in $(seq 1 "$RUNS"); do
  TAG=$PFX$i
  echo "== $(date +%T) run $TAG"
  one "$TAG"
  SN=$(saves); echo "$(date '+%F %T') after $TAG live saves $SN (want $WANT_SAVES)" >> "$R/catch-saves.txt"
  [ "$SN" = "$WANT_SAVES" ] || { echo "== $(date +%T) the live saves are not $WANT_SAVES after $TAG: the chain stops (snapshot $SNAP)"; break; }
  grep -q "^pass" "$R/$TAG-verdict.txt" 2> /dev/null || { echo "== $(date +%T) the chain stops after $TAG"; break; }
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/catch-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES: put them back by hand from $SNAP"
sync
grep -q "^exp 0281 | " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
