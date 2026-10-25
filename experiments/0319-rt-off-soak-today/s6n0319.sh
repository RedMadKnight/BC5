#!/usr/bin/env bash
# BC5 experiment 0319: does today's shared setup run an hour clean with RT off on S6N's route? Exp 0314's chain
# (s6n0314.sh: a derived launcher with a private working directory, its own _SaveData and log and a private input
# configuration; the live saves compared only, never written) on the shared normal build 226bcb82 with RT off:
# KYTY_BC5_RT=0, and RayTracing.PPSA03671=off in the private input configuration (the maintainer's saved setting would
# override the variable). The launcher is play-pkg.sh bb51caf2 (PlayGo F361, MangoHud hidden F367, the RT-off list with
# the three traversal programs F362, MALLOC_ARENA_MAX=2 F353, the cleanup fix), with no other change.
# Crash frequency is the measurement, so a crash or a recovered hang is recorded and the chain goes on. It stops on the
# machine-down class (reset failed / MODE1), on a live-save change, or when a run is not what it claims to be (wrong
# binary, private directories not taken, not on the route, RT not off). A box freeze ends everything by itself: the
# laptop's stream0319.sh and sample0319.sh hold the record.
# Per run: duration, how it ended, the launcher's exit status and the crash lines, kernel lines, TIMEOUT lines, flips/s
# (the journal's "VideoOutSubmitFlip took" lines over their span), the RT-off drop lines.
# On HUP/INT/TERM (a dropped ssh session) only this run's emulator is stopped; nothing else needs undoing.
# usage: s6n0319.sh [runs] [secs] [first] [expected live-saves sum]   (on the box)
set -u
RUNS=${1:-6}; SECS=${2:-600}; FIRST=${3:-1}; EXPECT_SAVES=${4:-bb14b6dd35b644ff}
E=$HOME/bc5-work/exp0319; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
SHARED=$W/kytyplus-build/src/kyty_emulator; WANT=226bcb82   # today's normal build; the launcher runs it by default
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617   # the live saves (read only) and the route's (exp 0196)
LAUNCH_SRC=$W/play-pkg.sh; L99=$W/exp0299/play-pkg-0299.sh; LAUNCH=$E/play-pkg-0319.sh
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$SHARED" | cut -c1-8)" = "$WANT" ] || { echo "$SHARED is not md5 $WANT: not started"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] || { echo "no $SAVES, $LAUNCH_SRC or o2-continue.cmd"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started (the maintainer saved since? pass the new sum as the 4th argument)"; exit 1; }
# 1. The private input configuration: the maintainer's file (read) with ray tracing off for this title.
CFG_SRC=$W/input.cfg; CFG=$E/input-rtoff.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=off"; } > "$CFG" || { echo "could not write $CFG"; exit 1; }
echo "private input config $CFG: $(grep -c . "$CFG") lines, $(grep -i "^RayTracing\." "$CFG" | tr '\n' ' ') (source $CFG_SRC, $(grep -i "^RayTracing\.PPSA03671=" "$CFG_SRC" || echo "no RayTracing.PPSA03671 line"))"
# 2. The derived launcher: play-pkg.sh + exp 0299's four edits renamed 0299 -> 0319 (own log, private working directory,
#    private KYTY_BC5_SAVEDATA_DIR, the input-config override); every anchor must occur exactly once.
SRC_MD5=$(md5sum < "$LAUNCH_SRC" | cut -c1-8)
[ "$SRC_MD5" = bb51caf2 ] || { echo "$LAUNCH_SRC is md5 $SRC_MD5, not bb51caf2 (today's, exp 0315): not started"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || { echo "could not copy $LAUNCH_SRC"; exit 1; }
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0319/play-last.log  \# exp 0319: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0319/wd  \# exp 0319: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0319/wd/_SaveData-pkg-play  \# exp 0319: private#' \
       -e '/^done < "\$ENVF"$/a [ -n "${BC5_0319_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0319_INPUT_CONFIG  # exp 0319: the private input configuration' "$LAUNCH" || { echo "sed failed"; exit 1; }
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0319.diff"
NCH=$(grep -c '^[-+][^-+]' "$R/play-pkg-0319.diff")
[ "$NCH" = 7 ] || { echo "the derived launcher differs in $NCH lines, expected 7: look at $R/play-pkg-0319.diff, not started"; exit 1; }
chmod +x "$LAUNCH"
eval "LOG=$(sed -n 's/^LOG=//p' "$LAUNCH" | head -1)"; [ -n "${LOG:-}" ] || { echo "no LOG= line in the derived launcher: not started"; exit 1; }
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"; [ -n "${SDD:-}" ] || { echo "no KYTY_BC5_SAVEDATA_DIR= in the derived launcher: not started"; exit 1; }
case "$SDD" in "$E"/*) ;; *) echo "the derived launcher's save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the derived launcher's log $LOG is not under $E: not started"; exit 1 ;; esac
# The working directory, laid out as exp 0299's: its own _SaveData, every other entry a symlink into ~/bc5-work. The title
# reads its saves cwd-relative (_SaveData/PPSA03671; exp 0314's note), so the route's saves go there.
WDL=$(grep -E '^[[:space:]]*cd .*exp0319' "$LAUNCH" | head -1 | sed -E 's/^[[:space:]]*cd +//; s/^"//; s/"[[:space:]]*$//')
[ -n "$WDL" ] || { echo "no cd into exp0319 in the derived launcher: not started"; exit 1; }
eval "WD=$WDL"; case "$WD" in "$E"/*) ;; *) echo "the derived launcher's working directory $WD is not under $E: not started"; exit 1 ;; esac
WD99=$(dirname "$L99")/wd; [ -d "$WD99" ] || { echo "no $WD99 to take the layout from: not started"; exit 1; }
mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
for e in "$WD99"/* "$WD99"/.[!.]*; do
  { [ -e "$e" ] || [ -L "$e" ]; } || continue
  n=$(basename "$e"); [ "$n" = _SaveData ] && continue
  if [ -L "$e" ]; then t=$(readlink "$e"); elif [ -e "$W/$n" ]; then t=$W/$n; else echo "exp 0299's wd entry $n is neither a symlink nor in $W: not started"; exit 1; fi
  t=${t//exp0299/exp0319}
  if [ -L "$WD/$n" ] && [ "$(readlink "$WD/$n")" = "$t" ]; then :; else rm -rf "$WD/$n" && ln -s "$t" "$WD/$n" || { echo "could not link $WD/$n -> $t"; exit 1; }; fi
done
SROOT=$WD/_SaveData
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
[ "$ATIME_OK" = 1 ] || echo "WARNING: $E is on a noatime mount: the route-save check at 60 s can only warn, not stop a run"
echo "launcher $LAUNCH (md5 $(md5sum < "$LAUNCH" | cut -c1-8)) from $LAUNCH_SRC bb51caf2 + exp 0299's edits renamed; log $LOG; diff $R/play-pkg-0319.diff"
echo "working directory $WD: $(ls -A "$WD" | wc -l) entries, $(find "$WD" -maxdepth 1 -type l | wc -l) symlinks (layout of $WD99: $(ls -A "$WD99" | wc -l) entries); the title's saves $SROOT/PPSA03671 (private); KYTY_BC5_SAVEDATA_DIR $SDD"
# 3. The live saves: snapshot for the comparison only; never written.
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only, nothing is restored into $SD)" | tee -a "$R/s6n-saves.txt"
echo "exp 0319 | s6n run: the second title's S6N route, RT off, shared normal $WANT, private wd $E, up to $RUNS x $SECS s, crashes and recovered hangs go on | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0319 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
EP=""
abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass, CRASH: ..., HANG: ..., DOWN: ... or FAIL: ...
  local TAG=$1 N T0 ENDED="" J NK NC NT NRT FAIL="" HANG="" CRASH="" DOWN="" ROUTED="" RTOFF="" FL SPAN FPS
  EP=""
  [ -e "$R/$TAG-start.txt" ] && { echo "FAIL: tag $TAG already used"; return; }
  case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "FAIL: refusing to clear $SROOT"; return ;; esac
  cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "FAIL: the route saves could not be put into $SROOT"; return; }
  find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
  echo "route saves $SAVES -> $SROOT/PPSA03671 ($(find "$SROOT/PPSA03671" -type f | wc -l) files, atime set back)" > "$R/$TAG-saves.txt"
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  N=$(sudo -n dmesg 2> /dev/null | wc -l)
  { date '+%F %T'; echo "run $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) (from $LAUNCH_SRC $(md5sum < "$LAUNCH_SRC" | cut -c1-8)), shared normal $SHARED md5 $WANT, input config $CFG, saves $SROOT"
    echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; boxstate start; } > "$R/$TAG-start.txt"
  # the launcher's exit status lands in <tag>-launch.out ("launcher exit N")
  setsid nohup bash -c 'distrobox enter ubuntu -- env KYTY_BC5_RT=0 BC5_0319_INPUT_CONFIG="$1" KYTY_BC5_INPUT_CMD="$2" "$3"; echo "launcher exit $?"' _ "$CFG" "$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|BC5_DIRECT_SKIP_PGM|BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_MEC_INDIRECT|BC5_DIRECT_GPU_CHECK|MALLOC_ARENA_MAX|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_INPUT_CONFIG=$CFG" || ENDED="SETUP: the emulator did not take the private input config $CFG"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_SAVEDATA_DIR=$SDD" || ENDED="SETUP: the emulator did not take the private save directory $SDD"
    [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory $(readlink "/proc/$EP/cwd") is not $WD (its saves would be the live ones)"
  fi
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
      if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1; echo "route save read by $(($(date +%s) - T0)) s: $(find "$SROOT/PPSA03671" -type f -newerat "@$T0" | wc -l) file(s) with a new atime" >> "$R/$TAG-saves.txt"
      elif [ "$ATIME_OK" = 1 ]; then ENDED="SETUP: the route save in $SROOT/PPSA03671 was not read by 60 s: the run is not on the route"; break
      else ROUTED=warned; echo "WARNING: no file's atime moved by 60 s, but the mount is noatime" | tee -a "$R/$TAG-saves.txt"; fi
    fi
    if [ -z "$RTOFF" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
      J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
      if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ] && grep -aq "ray tracing off:" "$J"; then RTOFF=1
      else ENDED="SETUP: no RT-off drop line by 180 s in $J: ray tracing is not off"; break; fi
    fi
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
      sleep 25  # the kernel's verdict: a recovered ring hang (reset succeeded) keeps the box up
      if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then
        ENDED="DOWN: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, reset failed or MODE1"
      elif sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then
        ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, ring reset succeeded"
      else
        ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, no reset line"
      fi
      break
    fi
    sleep 5
  done
  boxstate end > "$R/$TAG-box-end.txt"
  local DUR=$(($(date +%s) - T0))
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  sleep 3
  echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
  if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
  grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
  J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  NRT=0; FL=0; SPAN=0; FPS=0
  if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
    { echo "journal $J $(stat -c '%y %s' "$J")"
      [ -f "$W/exp0254/jcount0254.awk" ] && nice -n 19 awk -f "$W/exp0254/jcount0254.awk" "$J"; } > "$R/$TAG-journal.txt"
    nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
    NRT=$(nice -n 19 grep -a -c "ray tracing off:" "$J")
    read -r FL SPAN <<< "$(nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/.*t \([0-9.]*\) s.*/\1/p' | awk 'NR == 1 {a = $1} {b = $1; n++} END {printf "%d %.1f\n", n, b - a}')"
    FPS=$(awk -v n="${FL:-0}" -v s="${SPAN:-0}" 'BEGIN {printf "%.1f", s > 0 ? n / s : 0}')
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  echo "private saves after the run: $(find "$SROOT/PPSA03671" -type f 2> /dev/null | wc -l) files$(diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null 2>&1 && echo ", identical to the route's" || echo ", changed by the run (the title saves)")" >> "$R/$TAG-saves.txt"
  NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  sleep 2
  local LX; LX=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
  echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${LX:-launcher still running or no exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), RT-off drop lines $NRT, flips $FL over ${SPAN} s = $FPS flips/s; first crash line: $(grep -a -m1 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt" | cut -c1-160)" > "$R/$TAG-summary.txt"
  case "$ENDED" in
    "") ;;
    SETUP:*) FAIL="$FAIL ${ENDED#SETUP: };" ;;
    DOWN:*) DOWN="${ENDED#DOWN: }" ;;
    HANG:*) HANG="${ENDED#HANG: }" ;;
    "ended by itself"*) CRASH="$ENDED" ;;
  esac
  [ "$NC" = 0 ] || CRASH="${CRASH:-crash lines} ($NC crash lines)"
  if [ -n "$FAIL" ]; then echo "FAIL:$FAIL"; elif [ -n "$DOWN" ]; then echo "DOWN: $DOWN"; elif [ -n "$HANG" ]; then echo "HANG: $HANG"; elif [ -n "$CRASH" ]; then echo "CRASH: $CRASH"; else echo pass; fi > "$R/$TAG-verdict.txt"
  sync
  cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"
}
for i in $(seq "$FIRST" $((FIRST + RUNS - 1))); do
  TAG=S$i
  echo "== $(date +%T) run $TAG"
  one "$TAG"
  SN=$(saves); echo "$(date '+%F %T') after $TAG live saves $SN (want $WANT_SAVES)" >> "$R/s6n-saves.txt"
  [ "$SN" = "$WANT_SAVES" ] || { echo "== $(date +%T) THE LIVE SAVES CHANGED after $TAG ($SN, want $WANT_SAVES; snapshot $SNAP): the chain stops"; break; }
  grep -q "^FAIL\|^DOWN" "$R/$TAG-verdict.txt" 2> /dev/null && { echo "== $(date +%T) the chain stops after $TAG"; break; }
  grep -q "^HANG\|^CRASH" "$R/$TAG-verdict.txt" 2> /dev/null && echo "== $(date +%T) $TAG: $(cut -c1-60 "$R/$TAG-verdict.txt"); the chain goes on"
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot of the start: $SNAP): tell the maintainer before anything is restored"
sync
grep -q "^exp 0319 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
