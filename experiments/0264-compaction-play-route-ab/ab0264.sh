#!/usr/bin/env bash
# BC5 experiment 0264: the BVH compaction 0x909974400 on the second title's play route (the box supervisor's design,
# 2026-10-24). Exp 0260's catch0260.sh (the TCP session's) with these changes:
#   - the shared normal build through play-pkg.sh with its defaults (no BC5_EMU); every run's /proc/<pid>/exe md5 must
#     match the md5 the shared binary had at the chain's start;
#   - two arms, interleaved A B A B: A = the launcher's default (BC5_DIRECT_SKIP_PGM=909974400, the compaction skipped),
#     B = BC5_DIRECT_SKIP_PGM=1 (nothing skipped); the value is checked in the emulator's environment;
#   - screenshots at fixed seconds after the emulator starts (exp 0191's spectacle call) into raw/<tag>-shots/;
#   - after each run, the journal lines the frame statistics need (frame profile, skip pgm, flat aperture, TIMEOUT,
#     give-ups) are kept gzipped as raw/<tag>-x.gz.
# Route and saves as exp 0260: S6N's route (exp 0203's o2-continue.cmd: Continue at 85 s) from exp 0196's
# saves-before-152617, put in and taken back by exp 0196's ab-restore.sh. The live saves' checksum (the md5 of the sorted
# per-file md5s of PPSA03671) must be db52cb5f327c3de5 (the state after the 15:19 move of F319's stray .blocks sidecars) before the chain and after it. The chain stops after the first run
# that is not a pass: a new kernel amdgpu line (checked every 5 s; the run is stopped at once), a TIMEOUT in its journal,
# a crash line, the wrong binary or switch, or saves that did not come back. Only the emulator PID a run started is
# ever stopped. Attended: on the box supervisor's GO, the maintainer reachable for a power-cycle, stream0264.sh running
# on the laptop. After a machine-down the live saves are in exp0196/saves-before-* (the run's KEEP, named in
# <tag>-restore.txt): put them back by hand with ab-restore.sh <KEEP> and check the checksum.
# usage: ab0264.sh [secs] [shot seconds...]   (on the box; default 300 s, shots at 120 180 240 290)
set -u
SECS=${1:-300}; shift || true
SHOTS=${*:-120 180 240 290}
E=$HOME/bc5-work/exp0264; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$W/kytyplus-build/src/kyty_emulator; WANT_SAVES=db52cb5f327c3de5
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-last.log
mkdir -p "$R"
[ "$SECS" -le 600 ] || { echo "at most 600 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH" ] && [ -x "$W/exp0196/ab-restore.sh" ] || { echo "no $SAVES, $LAUNCH or ab-restore.sh"; exit 1; }
WANT=$(md5sum < "$BIN" | cut -c1-8)
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
S0=$(saves); echo "$(date '+%F %T') live saves $S0 (want $WANT_SAVES); shared binary md5 $WANT ($(stat -c %y "$BIN" | cut -c1-16))" | tee -a "$R/ab-saves.txt"
[ "$S0" = "$WANT_SAVES" ] || { echo "the live saves are not $WANT_SAVES: not started"; exit 1; }
echo "exp 0264 | ab run: the second title's S6N route, A/B of the BVH compaction (SKIP_PGM 909974400 vs 1), 4 x $SECS s, shared build, maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$((4 * (SECS + 70) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0264 | ab run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)" \
    "psi_mem_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)"
}
one() {  # <tag> <arm>: one run of the route; prints its summary and verdict
  local TAG=$1 ARM=$2 OUT KEEP N EP T0 ENDED="" J NK NC NT FAIL="" SKIP WANTSKIP SH t
  [ -e "$R/$TAG-start.txt" ] && { echo "FAIL: tag $TAG already used" | tee "$R/$TAG-verdict.txt"; return; }
  case $ARM in A) SKIP=""; WANTSKIP=909974400 ;; B) SKIP="BC5_DIRECT_SKIP_PGM=1"; WANTSKIP=1 ;; esac
  sleep 2  # ab-restore.sh names its copies by time
  OUT=$("$W/exp0196/ab-restore.sh" "$SAVES") || { echo "FAIL: route saves not put in: $OUT" | tee "$R/$TAG-verdict.txt"; return; }
  echo "$OUT" > "$R/$TAG-restore.txt"
  KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
  [ -d "$KEEP" ] || { echo "FAIL: the live saves were not kept" | tee "$R/$TAG-verdict.txt"; return; }
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  N=$(sudo -n dmesg 2> /dev/null | wc -l)
  { date '+%F %T'; echo "run $TAG, arm $ARM ('${SKIP:-launcher default}'), $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), binary $BIN md5 $WANT"
    echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; boxstate start; } > "$R/$TAG-start.txt"
  # shellcheck disable=SC2086
  setsid nohup distrobox enter ubuntu -- env -u BC5_EMU $SKIP KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe")" >> "$R/$TAG-start.txt"
    sleep 2
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_SKIP_PGM|BC5_DIRECT_FLAT_APERTURE|BC5_DIRECT_AMM_PRT|BC5_DIRECT_GC_TF_RING|BC5_DIRECT_HOLD_TAIL|BC5_DIRECT_CS_PREFIX|KYTY_BC5_TILER_POOL|PLAY_CAPTURE|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "BC5_DIRECT_SKIP_PGM=$WANTSKIP" || ENDED="${ENDED:-BC5_DIRECT_SKIP_PGM is not $WANTSKIP}"
  fi
  SH=$R/$TAG-shots; mkdir -p "$SH"
  set -- $SHOTS
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu" && { ENDED="kernel amdgpu line at $(($(date +%s) - T0)) s"; break; }
    if [ $# -gt 0 ] && [ $(($(date +%s) - T0)) -ge "$1" ]; then  # exp 0191's shots.sh call
      XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$SH/t$(printf %03d "$1").png" > /dev/null 2>&1 || true
      shift
    fi
    sleep 1
  done
  boxstate end > "$R/$TAG-box-end.txt"
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  sleep 3
  echo "$TAG ${ENDED:-stopped at $SECS s}" > "$R/$TAG-end.txt"
  cp -p "$LOG" "$R/$TAG-play.log" 2> /dev/null
  grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt" 2> /dev/null
  J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
    LC_ALL=C nice -n 19 grep -a -E "^frame profile: t |skip pgm|flat aperture|TIMEOUT|timeout: |GIVEN UP|NOT served|^cs prefix" "$J" | gzip > "$R/$TAG-x.gz"
    zcat "$R/$TAG-x.gz" | grep -a "TIMEOUT" > "$R/$TAG-probe.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  sleep 2
  "$W/exp0196/ab-restore.sh" "$KEEP" > "$R/$TAG-restore-back.txt" 2>&1
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then echo "NESTED SAVE COPY in $KEEP or $SD" >> "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" >> "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" >> "$R/$TAG-restore-back.txt"; fi
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG (arm $ARM): ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, shots $(ls "$SH" | grep -c png)" > "$R/$TAG-summary.txt"
  case "$ENDED" in "" ) ;; *) FAIL="$FAIL $ENDED;" ;; esac
  [ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
  [ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
  [ "$NT" = 0 ] || FAIL="$FAIL $NT TIMEOUT lines;"
  grep -q "live saves back and identical" "$R/$TAG-restore-back.txt" || FAIL="$FAIL THE LIVE SAVES NEED CHECKING;"
  if [ -z "$FAIL" ]; then echo pass; else echo "FAIL:$FAIL"; fi > "$R/$TAG-verdict.txt"
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for spec in A1:A B1:B A2:A B2:B; do
  TAG=${spec%%:*}; ARM=${spec##*:}
  echo "== $(date +%T) run $TAG (arm $ARM)"
  one "$TAG" "$ARM"
  grep -q "^pass" "$R/$TAG-verdict.txt" 2> /dev/null || { echo "== $(date +%T) the chain stops after $TAG"; break; }
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/ab-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES: put them back by hand"
grep -q "^exp 0264 | ab run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
