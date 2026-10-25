#!/usr/bin/env bash
# BC5 experiment 0302: the S6N runs with the private binary that reads the resource table of the F360 family's
# dispatches at filter time and compares it at the fence timeout (patch0302.py; diagnostic (a), no sync packets, no
# refusal change — the archive is build0302.sh's argument). Exp 0300's s6n0300.sh with the sync part taken out:
#   - ray tracing ON through a private copy of the maintainer's input configuration (RayTracing.PPSA03671=on; his file is
#     only read) handed through BC5_0302_INPUT_CONFIG to a derived launcher, exp0302/play-pkg-0302.sh = today's play-pkg.sh
#     (md5 fde58cda) + exactly exp 0299's edits renamed (its diff against play-pkg.sh, 0299 -> 0302, applied with the ubuntu
#     distrobox's patch(1), -F0: a moved anchor stops the chain): the input-config re-export after the bc5-run.env export
#     loop, its own log, a `cd` into the private working directory and KYTY_BC5_SAVEDATA_DIR into it;
#   - the working directory laid out as exp 0299's (own _SaveData, every other entry a symlink into ~/bc5-work); exp 0196's
#     route saves copied into ITS _SaveData/PPSA03671 before each run (the title reads its saves cwd-relative) with their
#     atime set back; the emulator's cwd must be that directory; a run stops at 60 s unless a save file's atime moved;
#   - NO live-save flow: the maintainer's live saves are snapshot at chain start for the comparison only and their sum must
#     read EXPECT_SAVES (4th argument, default 8289704a9338a118) at the start, after every run and at the end; nothing is
#     ever restored into the live directory;
#   - up to 2 runs of 600 s (default): without the sync packets the hang came at ~2 min in every exp 0290 run, and each hang
#     of this class has been a machine-down (comp_1.1.0 reset failed, MODE1), so each run is one power-cycle away — the
#     supervisor sets the count, the maintainer reachable; the chain stops on a failed reset / MODE1, a crash, or a
#     live-save change; a recovered hang is recorded as HANG and the chain goes on;
#   - three checks that ray tracing is really on: the emulator's environment carries KYTY_BC5_INPUT_CONFIG=<the private copy>
#     and KYTY_BC5_SAVEDATA_DIR=<the private dir> (else the run stops at once), the log does not say "ray tracing off" in the
#     first 90 s, and the journal has a "descriptor (exp 0302)" line by 180 s (a listed dispatch seen);
#   - extracts per run: the probe's lines, the "descriptor (exp 0302)" (<tag>-sync.txt) and "table (exp 0302)" lines, the
#     ray-tracing lines, dmesg, the devcoredump paths (never the dumps).
# Only the emulator PID a run started is ever stopped. Attended: on the box supervisor's GO, daytime, the maintainer
# reachable for a power-cycle, stream0302.sh on the laptop. After a machine-down nothing needs restoring: the live saves
# were never touched (their snapshot is exp0302/saves-before-<HHMM>, for the comparison only).
# usage: s6n0302.sh [runs] [secs] [first] [expected live-saves sum]   (on the box)
set -u
RUNS=${1:-2}; SECS=${2:-600}; FIRST=${3:-1}; EXPECT_SAVES=${4:-8289704a9338a118}
E=$HOME/bc5-work/exp0302; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2>/dev/null)   # written by build0302.sh
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617   # the live saves (read only) and the route's (exp 0196)
LAUNCH_SRC=$W/play-pkg.sh; L99=$W/exp0299/play-pkg-0299.sh; LAUNCH=$E/play-pkg-0302.sh
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -r "$L99" ] || { echo "no $SAVES, $LAUNCH_SRC or $L99"; exit 1; }
if command -v patch > /dev/null; then PATCH=patch; else PATCH="distrobox enter ubuntu -- patch"; fi   # the Bazzite host has no patch(1); the ubuntu distrobox has, same $HOME
$PATCH --version > /dev/null 2>&1 || { echo "no patch(1) on the host or in the ubuntu distrobox: not started"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started (the maintainer saved since? pass the new sum as the 4th argument)"; exit 1; }
# 1. The private input configuration: the maintainer's file (read) with ray tracing on for this title.
CFG_SRC=$W/input.cfg; CFG=$E/input-rt.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=on"; } > "$CFG" || { echo "could not write $CFG"; exit 1; }
echo "private input config $CFG: $(grep -c . "$CFG") lines, $(grep -i "^RayTracing\." "$CFG" | tr '\n' ' ') (source $CFG_SRC, $(grep -i "^RayTracing\.PPSA03671=" "$CFG_SRC" || echo "no RayTracing.PPSA03671 line"))"
# 2. The derived launcher: play-pkg.sh + exp 0299's edits renamed 0299 -> 0302, by patch(1) (an anchor that moved fails it).
[ "$(md5sum < "$LAUNCH_SRC" | cut -c1-8)" = fde58cda ] || { echo "$LAUNCH_SRC is not fde58cda (the launcher changed since 2026-10-25): check exp 0299's edits against it again, not started"; exit 1; }
diff -u "$LAUNCH_SRC" "$L99" > "$R/play-pkg-0299.diff"; [ -s "$R/play-pkg-0299.diff" ] || { echo "$L99 does not differ from $LAUNCH_SRC: not started"; exit 1; }
grep -q 'BC5_0299_INPUT_CONFIG' "$R/play-pkg-0299.diff" && grep -q 'KYTY_BC5_SAVEDATA_DIR' "$R/play-pkg-0299.diff" && grep -qE '^\+.*\bcd\b' "$R/play-pkg-0299.diff" \
  || { echo "exp 0299's diff lacks the input-config override, the KYTY_BC5_SAVEDATA_DIR line or the cd: look at $R/play-pkg-0299.diff, not started"; exit 1; }
grep -c '^[-+][^-+]' "$R/play-pkg-0299.diff" | sed 's/^/exp 0299 changed lines: /'
sed 's/0299/0302/g' "$R/play-pkg-0299.diff" > "$R/play-pkg-0302.diff"
cp "$LAUNCH_SRC" "$LAUNCH" && $PATCH --silent --no-backup-if-mismatch -F0 "$LAUNCH" "$R/play-pkg-0302.diff" || { echo "exp 0299's edits do not apply to $LAUNCH_SRC with the rename: not started"; rm -f "$LAUNCH"; exit 1; }
chmod +x "$LAUNCH"
grep -q 'BC5_0302_INPUT_CONFIG' "$LAUNCH" && ! grep -q '0299' "$LAUNCH" || { echo "the derived launcher still names 0299 or lacks BC5_0302_INPUT_CONFIG: not started"; exit 1; }
eval "LOG=$(sed -n 's/^LOG=//p' "$LAUNCH" | head -1)"; [ -n "${LOG:-}" ] || { echo "no LOG= line in the derived launcher: not started"; exit 1; }
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"; [ -n "${SDD:-}" ] || { echo "no KYTY_BC5_SAVEDATA_DIR= in the derived launcher: not started"; exit 1; }
case "$SDD" in "$E"/*) ;; *) echo "the derived launcher's save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the derived launcher's log $LOG is not under $E: not started"; exit 1 ;; esac
# The working directory the derived launcher cd's into, laid out as exp 0299's (exp 0194's bench): its own _SaveData,
# every other entry a symlink into ~/bc5-work. The title reads its saves cwd-relative, _SaveData/PPSA03671 (the
# supervisor, 2026-10-25: today's play wrote ~/bc5-work/_SaveData, not play-pkg.sh's KYTY_BC5_SAVEDATA_DIR), so the
# route's saves go there; the KYTY_BC5_SAVEDATA_DIR directory is created too but not relied on.
WDL=$(grep -E '^[[:space:]]*cd .*exp0302' "$LAUNCH" | head -1 | sed -E 's/^[[:space:]]*cd +//; s/^"//; s/"[[:space:]]*$//')
[ -n "$WDL" ] || { echo "no cd into exp0302 in the derived launcher: not started"; exit 1; }
eval "WD=$WDL"; case "$WD" in "$E"/*) ;; *) echo "the derived launcher's working directory $WD is not under $E: not started"; exit 1 ;; esac
WD99=$(dirname "$L99")/wd; [ -d "$WD99" ] || { echo "no $WD99 to take the layout from: not started"; exit 1; }
mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
for e in "$WD99"/* "$WD99"/.[!.]*; do
  { [ -e "$e" ] || [ -L "$e" ]; } || continue
  n=$(basename "$e"); [ "$n" = _SaveData ] && continue
  if [ -L "$e" ]; then t=$(readlink "$e"); elif [ -e "$W/$n" ]; then t=$W/$n; else echo "exp 0299's wd entry $n is neither a symlink nor in $W: not started"; exit 1; fi
  t=${t//exp0299/exp0302}   # a private entry of 0299's would get a 0302 twin (none expected beyond _SaveData)
  if [ -L "$WD/$n" ] && [ "$(readlink "$WD/$n")" = "$t" ]; then :; else rm -rf "$WD/$n" && ln -s "$t" "$WD/$n" || { echo "could not link $WD/$n -> $t"; exit 1; }; fi
done
SROOT=$WD/_SaveData
# relatime (the kernel's default) moves a file's atime on the first read once it lies before the mtime; a noatime mount
# never does, and then the 60-s route check below can only warn.
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
[ "$ATIME_OK" = 1 ] || echo "WARNING: $E is on a noatime mount: the route-save check at 60 s can only warn, not stop a run"
echo "launcher $LAUNCH (md5 $(md5sum < "$LAUNCH" | cut -c1-8)) from $LAUNCH_SRC fde58cda + exp 0299's edits renamed; log $LOG; diff $R/play-pkg-0302.diff"
echo "working directory $WD: $(ls -A "$WD" | wc -l) entries, $(find "$WD" -maxdepth 1 -type l | wc -l) symlinks (layout of $WD99: $(ls -A "$WD99" | wc -l) entries); the title's saves $SROOT/PPSA03671 (private); KYTY_BC5_SAVEDATA_DIR $SDD"
# 3. The live saves: snapshot for the comparison only; never written.
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only, nothing is restored into $SD)" | tee -a "$R/s6n-saves.txt"
echo "exp 0302 | s6n run: the second title's S6N route, RT on, private wd $E, up to $RUNS x $SECS s, exp0302 binary (descriptor check of the F360 family's dispatches: filter-time table snapshot, compared at the timeout; no sync packets), maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0302 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass, HANG: ... or FAIL: ...
  local TAG=$1 N EP T0 ENDED="" J NK NC NT FAIL="" HANG="" RECOVERED="" DOWN="" LISTED="" ROUTED=""
  [ -e "$R/$TAG-start.txt" ] && { echo "FAIL: tag $TAG already used"; return; }
  # the route's saves into the private working directory's _SaveData (the live directory is not touched); their atime
  # set back so that relatime updates it on the first read — the 60-s check below that the title really took them
  case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "FAIL: refusing to clear $SROOT"; return ;; esac
  cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "FAIL: the route saves could not be put into $SROOT"; return; }
  find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
  echo "route saves $SAVES -> $SROOT/PPSA03671 ($(find "$SROOT/PPSA03671" -type f | wc -l) files, atime set back)" > "$R/$TAG-saves.txt"
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  N=$(sudo -n dmesg 2> /dev/null | wc -l)
  { date '+%F %T'; echo "run $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) (from $LAUNCH_SRC $(md5sum < "$LAUNCH_SRC" | cut -c1-8)), BC5_EMU $BIN md5 $WANT, input config $CFG, saves $SDD, table list default (the 0x11d03a family)"
    echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; boxstate start; } > "$R/$TAG-start.txt"
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 KYTY_BC5_RT=1 BC5_0302_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_MEC_INDIRECT|BC5_DIRECT_COMPUTE_RING|KYTY_BC5_RT|KYTY_BC5_INPUT_CONFIG|BC5_0302_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_RT_DETECT|KYTY_BC5_TILER_POOL|PLAY_CAPTURE|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"  # by content: /home is /var/home on the box
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_INPUT_CONFIG=$CFG" || ENDED="the emulator did not take the private input config $CFG (ray tracing would stay off): run stopped"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_SAVEDATA_DIR=$SDD" || ENDED="the emulator did not take the private save directory $SDD: run stopped"
    [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="the emulator's working directory $(readlink "/proc/$EP/cwd") is not $WD (its saves would be the live ones): run stopped"
  fi
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    if [ $(($(date +%s) - T0)) -lt 90 ] && grep -aq "ray tracing off" "$LOG" 2> /dev/null; then
      ENDED="the log says ray tracing off (the title's saved configuration overrode it): run stopped at $(($(date +%s) - T0)) s"; break
    fi
    if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
      if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1; echo "route save read by $(($(date +%s) - T0)) s: $(find "$SROOT/PPSA03671" -type f -newerat "@$T0" | wc -l) file(s) with a new atime" >> "$R/$TAG-saves.txt"
      elif [ "$ATIME_OK" = 1 ]; then ENDED="the route save in $SROOT/PPSA03671 was not read by 60 s (no file's atime moved): the run is not on the route: run stopped"; break
      else ROUTED=warned; echo "WARNING: no file's atime moved by 60 s, but the mount is noatime: cannot tell whether the route save was read" | tee -a "$R/$TAG-saves.txt"; fi
    fi
    if [ -z "$LISTED" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
      J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
      if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ] && grep -aq "descriptor (exp 0302)" "$J"; then LISTED=1
      else ENDED="no listed dispatch reached the GPU by 180 s (no descriptor line in $J): ray tracing is not on or the list does not match: run stopped"; break; fi
    fi
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
      ENDED="kernel amdgpu line at $(($(date +%s) - T0)) s"
      sleep 25  # the kernel's verdict: a recovered GFX-ring hang (reset succeeded) keeps the box up
      if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then
        ENDED="MACHINE-DOWN CLASS: $ENDED, reset failed or MODE1"; DOWN=1
      elif sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then
        ENDED="recovered GFX-ring hang: $ENDED, ring reset succeeded"; RECOVERED=1
      else
        ENDED="kernel line without a reset: $ENDED"
      fi
      break
    fi
    sleep 5
  done
  boxstate end > "$R/$TAG-box-end.txt"
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  sleep 3
  echo "$TAG ${ENDED:-stopped at $SECS s}" > "$R/$TAG-end.txt"
  if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
  grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt" 2> /dev/null
  grep -a "ray tracing" "$R/$TAG-play.log" > "$R/$TAG-rt.txt" 2> /dev/null
  J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J")"
      [ -f "$W/exp0254/jcount0254.awk" ] && nice -n 19 awk -f "$W/exp0254/jcount0254.awk" "$J"; } > "$R/$TAG-journal.txt"
    nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
    nice -n 19 grep -a "descriptor (exp 0302)" "$J" > "$R/$TAG-sync.txt"
    nice -n 19 grep -a "table (exp 0302)" "$J" > "$R/$TAG-table.txt"
    nice -n 19 grep -a "ray tracing\|mec rebuild" "$J" >> "$R/$TAG-rt.txt"
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-sync.txt"; : > "$R/$TAG-table.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  # the maintainer's devcoredump copies (CLAUDE.md): paths and sizes only, the dumps are never copied out
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  echo "private saves after the run: $(find "$SROOT/PPSA03671" -type f 2> /dev/null | wc -l) files$(diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null 2>&1 && echo ", identical to the route's" || echo ", changed by the run (expected: the title saves)"); $(find "$SDD" -type f 2> /dev/null | wc -l) file(s) under KYTY_BC5_SAVEDATA_DIR $SDD" >> "$R/$TAG-saves.txt"
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG: ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, probe lines $(grep -c "timeout probe" "$R/$TAG-probe.txt"), sync lines $(grep -c . "$R/$TAG-sync.txt") (last: $(tail -1 "$R/$TAG-sync.txt" | sed 's/.*(\([0-9]* inserted so far\)).*/\1/')), table lines $(grep -c . "$R/$TAG-table.txt"), devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt")" > "$R/$TAG-summary.txt"
  case "$ENDED" in
    "") ;;
    recovered* | "kernel line"*) HANG="$HANG $ENDED;" ;;
    *) FAIL="$FAIL $ENDED;" ;;
  esac
  [ "$NC" = 0 ] || FAIL="$FAIL $NC crash lines;"
  [ "$NK" = 0 ] || [ -n "$RECOVERED" ] || [ -n "$HANG" ] || [ -n "$DOWN" ] || FAIL="$FAIL $NK kernel lines;"
  [ "$NT" = 0 ] || [ -n "$HANG" ] || [ -n "$DOWN" ] || FAIL="$FAIL $NT TIMEOUT lines;"   # the host's 2-s fence timeout is part of a hang
  if [ -n "$FAIL" ]; then echo "FAIL:$FAIL"; elif [ -n "$HANG" ]; then echo "HANG:$HANG"; else echo pass; fi > "$R/$TAG-verdict.txt"
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for i in $(seq "$FIRST" $((FIRST + RUNS - 1))); do
  TAG=S$i
  echo "== $(date +%T) run $TAG"
  one "$TAG"
  SN=$(saves); echo "$(date '+%F %T') after $TAG live saves $SN (want $WANT_SAVES)" >> "$R/s6n-saves.txt"
  [ "$SN" = "$WANT_SAVES" ] || { echo "== $(date +%T) THE LIVE SAVES CHANGED after $TAG ($SN, want $WANT_SAVES; snapshot $SNAP): the chain stops — the private save directory did not hold"; break; }
  grep -q "^FAIL" "$R/$TAG-verdict.txt" 2> /dev/null && { echo "== $(date +%T) the chain stops after $TAG"; break; }
  grep -q "^HANG" "$R/$TAG-verdict.txt" 2> /dev/null && echo "== $(date +%T) $TAG hung and the box recovered: the chain goes on"
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot of the start: $SNAP): tell the maintainer before anything is restored"
grep -q "^exp 0302 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
