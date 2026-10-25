#!/usr/bin/env bash
# BC5 experiment 0323, part 3 - the verification of the integrated ring ordering (int0323.sh: exp 0290's refusal in the
# shared archive, both shared emulators relinked, the three launchers with BC5_DIRECT_RING_DEPS=dcb and the compaction on).
# Exp 0306's chain (RT through a private input configuration and a derived launcher, private working directory with its
# own _SaveData, the live saves compared only) on the SHARED build through a copy of the integrated play-pkg.sh (its md5
# from exp0323/integration/new-md5.env), with the launcher's own defaults (no BC5_DIRECT_SKIP_PGM from here; the environ
# must show RING_DEPS=dcb, COMPUTE_RING=0, SKIP_PGM=0). Modes: rt-on (the S6N route, 2 x 600 s; the 180-s marker is the
# refusal's 'stays on the GFX ring' line - the shared build has no exp 0302 descriptor check), rt-off (RayTracing off in
# the configuration and KYTY_BC5_RT=0, 1 x 600 s, the flips against F382's 40.9-42.0/s), lean (the lean build, BC5_LEAN=1,
# no journal, a short start). fdinfo at ~121 s and at the end. The chain stops at the first machine-down (reset failed /
# MODE1), a crash, or a live-save change; a recovered hang = HANG, it goes on. The release leaves an empty BOX-LOCK.
# usage: ver0323.sh <rt-on|rt-off|lean> [runs] [secs] [first] [expected live-saves sum]   (on the box, on the GO)
set -u
MODE=${1:-rt-on}; RUNS=${2:-2}; SECS=${3:-600}; FIRST=${4:-1}; EXPECT_SAVES=${5:-bb14b6dd35b644ff}
case "$MODE" in rt-on | rt-off | lean) ;; *) echo "mode $MODE: rt-on, rt-off or lean"; exit 1 ;; esac
E=$HOME/bc5-work/exp0323; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
[ -s "$E/integration/new-md5.env" ] || { echo "no $E/integration/new-md5.env (int0323.sh has not run)"; exit 1; }
. "$E/integration/new-md5.env"   # archive= normal= lean= play_pkg= written by int0323.sh
if [ "$MODE" = lean ]; then BIN=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator; WANT=$lean; else BIN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator; WANT=$normal; fi   # the shared builds after int0323.sh
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617   # the live saves (read only) and the route's (exp 0196)
LAUNCH_SRC=$W/play-pkg.sh; L99=$W/exp0299/play-pkg-0299.sh; LAUNCH=$E/play-pkg-0323.sh
mkdir -p "$R"
[ "$SECS" -le 600 ] && [ "$RUNS" -le 6 ] || { echo "at most 6 runs of 600 s"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] || { echo "no $SAVES or $LAUNCH_SRC"; exit 1; }
if command -v patch > /dev/null; then PATCH=patch; else PATCH="distrobox enter ubuntu -- patch"; fi   # the Bazzite host has no patch(1); the ubuntu distrobox has, same $HOME
$PATCH --version > /dev/null 2>&1 || { echo "no patch(1) on the host or in the ubuntu distrobox: not started"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started (the maintainer saved since? pass the new sum as the 4th argument)"; exit 1; }
# 1. The private input configuration: the maintainer's file (read) with ray tracing on for this title.
CFG_SRC=$W/input.cfg; CFG=$E/input-rt.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=$([ "$MODE" = rt-off ] && echo off || echo on)"; } > "$CFG"  # exp 0323: the mode's RT setting; the shared build knows MangoHud — exp 0302's binary predates that control (exit 65 at 18:02) || { echo "could not write $CFG"; exit 1; }
echo "private input config $CFG: $(grep -c . "$CFG") lines, $(grep -i "^RayTracing\." "$CFG" | tr '\n' ' ') (source $CFG_SRC, $(grep -i "^RayTracing\.PPSA03671=" "$CFG_SRC" || echo "no RayTracing.PPSA03671 line"))"
# 2. The derived launcher: play-pkg.sh + exp 0299's edits renamed 0299 -> 0323, by patch(1) (an anchor that moved fails it).
SRC_MD5=$(md5sum < "$LAUNCH_SRC" | cut -c1-8)
case "$SRC_MD5" in "$play_pkg") ;; *) echo "$LAUNCH_SRC is md5 $SRC_MD5, not one checked today (fde58cda, ac7a9a57 the MangoHud integration, 628b2714 the lab fix): check exp 0299's edits against it again, not started"; exit 1 ;; esac
cp "$LAUNCH_SRC" "$LAUNCH" || { echo "could not copy $LAUNCH_SRC"; exit 1; }
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0323/play-last.log  \# exp 0323: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0323/wd  \# exp 0323: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0323/wd/_SaveData-pkg-play  \# exp 0323: private#' \
       -e '/^done < "\$ENVF"$/a [ -n "${BC5_0323_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0323_INPUT_CONFIG  # exp 0323: the private input configuration' "$LAUNCH" || { echo "sed failed"; exit 1; }
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0323.diff"
NCH=$(grep -c '^[-+][^-+]' "$R/play-pkg-0323.diff")
[ "$NCH" = 7 ] || { echo "the derived launcher differs in $NCH lines, expected 7: look at $R/play-pkg-0323.diff, not started"; exit 1; }
chmod +x "$LAUNCH"
grep -q 'BC5_0323_INPUT_CONFIG' "$LAUNCH" || { echo "the derived launcher lacks BC5_0323_INPUT_CONFIG: not started"; exit 1; }   # (play-pkg.sh 628b2714 itself mentions exp 0299 in a comment, so no "no 0299" check)
# exp 0323: the compaction runs — every assignment of BC5_DIRECT_SKIP_PGM in the derived launcher becomes =0, and one
# export of =0 goes right after the input-config override (after the bc5-run.env export loop); the emulator's environ is checked
sed -i -E 's/^([[:space:]]*(export[[:space:]]+)?)BC5_DIRECT_SKIP_PGM=.*$/\1BC5_DIRECT_SKIP_PGM=0  # exp 0323: the compaction 909974400 runs (was: the default skip)/' "$LAUNCH"
sed -i '/BC5_0323_INPUT_CONFIG:-/a export BC5_DIRECT_SKIP_PGM=0  # exp 0323: the compaction 909974400 runs' "$LAUNCH"
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0323-final.diff"
echo "skip list in the derived launcher: $(grep -n 'BC5_DIRECT_SKIP_PGM' "$LAUNCH" | cut -c1-120 | tr '\n' ';')"
eval "LOG=$(sed -n 's/^LOG=//p' "$LAUNCH" | head -1)"; [ -n "${LOG:-}" ] || { echo "no LOG= line in the derived launcher: not started"; exit 1; }
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"; [ -n "${SDD:-}" ] || { echo "no KYTY_BC5_SAVEDATA_DIR= in the derived launcher: not started"; exit 1; }
case "$SDD" in "$E"/*) ;; *) echo "the derived launcher's save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the derived launcher's log $LOG is not under $E: not started"; exit 1 ;; esac
# The working directory the derived launcher cd's into, laid out as exp 0299's (exp 0194's bench): its own _SaveData,
# every other entry a symlink into ~/bc5-work. The title reads its saves cwd-relative, _SaveData/PPSA03671 (the
# supervisor, 2026-10-25: today's play wrote ~/bc5-work/_SaveData, not play-pkg.sh's KYTY_BC5_SAVEDATA_DIR), so the
# route's saves go there; the KYTY_BC5_SAVEDATA_DIR directory is created too but not relied on.
WDL=$(grep -E '^[[:space:]]*cd .*exp0323' "$LAUNCH" | head -1 | sed -E 's/^[[:space:]]*cd +//; s/^"//; s/"[[:space:]]*$//')
[ -n "$WDL" ] || { echo "no cd into exp0323 in the derived launcher: not started"; exit 1; }
eval "WD=$WDL"; case "$WD" in "$E"/*) ;; *) echo "the derived launcher's working directory $WD is not under $E: not started"; exit 1 ;; esac
WD99=$(dirname "$L99")/wd; [ -d "$WD99" ] || { echo "no $WD99 to take the layout from: not started"; exit 1; }
mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
for e in "$WD99"/* "$WD99"/.[!.]*; do
  { [ -e "$e" ] || [ -L "$e" ]; } || continue
  n=$(basename "$e"); [ "$n" = _SaveData ] && continue
  if [ -L "$e" ]; then t=$(readlink "$e"); elif [ -e "$W/$n" ]; then t=$W/$n; else echo "exp 0299's wd entry $n is neither a symlink nor in $W: not started"; exit 1; fi
  t=${t//exp0299/exp0323}   # a private entry of 0299's would get a 0323 twin (none expected beyond _SaveData)
  if [ -L "$WD/$n" ] && [ "$(readlink "$WD/$n")" = "$t" ]; then :; else rm -rf "$WD/$n" && ln -s "$t" "$WD/$n" || { echo "could not link $WD/$n -> $t"; exit 1; }; fi
done
SROOT=$WD/_SaveData
# relatime (the kernel's default) moves a file's atime on the first read once it lies before the mtime; a noatime mount
# never does, and then the 60-s route check below can only warn.
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
[ "$ATIME_OK" = 1 ] || echo "WARNING: $E is on a noatime mount: the route-save check at 60 s can only warn, not stop a run"
echo "launcher $LAUNCH (md5 $(md5sum < "$LAUNCH" | cut -c1-8)) from $LAUNCH_SRC fde58cda + exp 0299's edits renamed; log $LOG; diff $R/play-pkg-0323.diff"
echo "working directory $WD: $(ls -A "$WD" | wc -l) entries, $(find "$WD" -maxdepth 1 -type l | wc -l) symlinks (layout of $WD99: $(ls -A "$WD99" | wc -l) entries); the title's saves $SROOT/PPSA03671 (private); KYTY_BC5_SAVEDATA_DIR $SDD"
# 3. The live saves: snapshot for the comparison only; never written.
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only, nothing is restored into $SD)" | tee -a "$R/s6n-saves.txt"
echo "exp 0323 | ver run ($MODE): the second title's S6N route, private wd $E, up to $RUNS x $SECS s, the shared $([ "$MODE" = lean ] && echo lean || echo normal) build $WANT through the integrated play-pkg.sh $play_pkg (RING_DEPS=dcb, the compaction on with RT), maintainer reachable | start $(date +%H:%M) | until ~$(date -d "+$((RUNS * (SECS + 60) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0323 | ver run" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
boxstate() {  # <label>: the box's memory state and pressure counters (exp 0229, as run0254b.sh)
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)"
}
one() {  # <tag>: one run of the route; prints pass, HANG: ... or FAIL: ...
  local TAG=$1 N EP T0 ENDED="" J NK NC NT FAIL="" HANG="" RECOVERED="" DOWN="" LISTED="" ROUTED="" FDINFO=""
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
  setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" BC5_DIRECT_TIMEOUT_PROBE=1 KYTY_BC5_RT=$([ "$MODE" = rt-off ] && echo 0 || echo 1) $([ "$MODE" = lean ] && echo BC5_LEAN=1) BC5_0323_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" "$LAUNCH" \
    < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  EP=""
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
    echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_SKIP_PGM|BC5_DIRECT_TIMEOUT_PROBE|BC5_DIRECT_MEC_INDIRECT|BC5_DIRECT_COMPUTE_RING|KYTY_BC5_RT|KYTY_BC5_INPUT_CONFIG|BC5_0323_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_RT_DETECT|KYTY_BC5_TILER_POOL|PLAY_CAPTURE|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="the emulator is not md5 $WANT"  # by content: /home is /var/home on the box
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_INPUT_CONFIG=$CFG" || ENDED="the emulator did not take the private input config $CFG (ray tracing would stay off): run stopped"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "KYTY_BC5_SAVEDATA_DIR=$SDD" || ENDED="the emulator did not take the private save directory $SDD: run stopped"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "BC5_DIRECT_SKIP_PGM=0" || ENDED="the emulator's BC5_DIRECT_SKIP_PGM is not 0 (the launcher's new default did not take): run stopped"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "BC5_DIRECT_COMPUTE_RING=0" || ENDED="the emulator's BC5_DIRECT_COMPUTE_RING is not 0: run stopped"
    tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qx "BC5_DIRECT_RING_DEPS=dcb" || ENDED="the emulator's BC5_DIRECT_RING_DEPS is not dcb (the launcher's new line did not take): run stopped"
    [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="the emulator's working directory $(readlink "/proc/$EP/cwd") is not $WD (its saves would be the live ones): run stopped"
  fi
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    if [ $(($(date +%s) - T0)) -ge $((SECS - 3)) ] && [ "$FDINFO" != 2 ]; then FDINFO=2; { echo "at $(($(date +%s) - T0)) s:"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } >> "$R/$TAG-fdinfo.txt"; fi
    if [ "$MODE" = rt-on ] && [ $(($(date +%s) - T0)) -lt 90 ] && grep -aq "ray tracing off" "$LOG" 2> /dev/null; then
      ENDED="the log says ray tracing off (the title's saved configuration overrode it): run stopped at $(($(date +%s) - T0)) s"; break
    fi
    if [ -z "$FDINFO" ] && [ $(($(date +%s) - T0)) -ge 120 ]; then  # exp 0323: the rings the title's work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)
      FDINFO=1; { echo "at $(($(date +%s) - T0)) s:"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } > "$R/$TAG-fdinfo.txt"
    fi
    if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
      if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1; echo "route save read by $(($(date +%s) - T0)) s: $(find "$SROOT/PPSA03671" -type f -newerat "@$T0" | wc -l) file(s) with a new atime" >> "$R/$TAG-saves.txt"
      elif [ "$ATIME_OK" = 1 ]; then ENDED="the route save in $SROOT/PPSA03671 was not read by 60 s (no file's atime moved): the run is not on the route: run stopped"; break
      else ROUTED=warned; echo "WARNING: no file's atime moved by 60 s, but the mount is noatime: cannot tell whether the route save was read" | tee -a "$R/$TAG-saves.txt"; fi
    fi
    if [ -z "$LISTED" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
      J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
      if [ "$MODE" != rt-on ]; then LISTED=1   # rt-off: no build work by design; lean: no journal
      elif [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ] && grep -aq "stays on the GFX ring" "$J"; then LISTED=1
      else ENDED="no refusal line in the journal by 180 s ($J): the build work is not reaching the GPU or the journal is elsewhere: run stopped"; break; fi
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
    nice -n 19 grep -a "skip pgm" "$J" > "$R/$TAG-skip.txt"
    nice -n 19 grep -a "909974400" "$J" | head -200 > "$R/$TAG-compaction.txt"
    nice -n 19 grep -a -i "flip" "$J" | tail -40 > "$R/$TAG-flips.txt"
    nice -n 19 grep -a "ray tracing\|mec rebuild" "$J" >> "$R/$TAG-rt.txt"
    ls -la "$(dirname "$J")" > "$R/$TAG-capture-dir.txt"
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-sync.txt"; : > "$R/$TAG-table.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  # the maintainer's devcoredump copies (CLAUDE.md): paths and sizes only, the dumps are never copied out
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  echo "private saves after the run: $(find "$SROOT/PPSA03671" -type f 2> /dev/null | wc -l) files$(diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null 2>&1 && echo ", identical to the route's" || echo ", changed by the run (expected: the title saves)"); $(find "$SDD" -type f 2> /dev/null | wc -l) file(s) under KYTY_BC5_SAVEDATA_DIR $SDD" >> "$R/$TAG-saves.txt"
  NC=$(grep -c . "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  echo "$TAG: ${ENDED:-stopped at $SECS s}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, probe lines $(grep -c "timeout probe" "$R/$TAG-probe.txt"), sync lines $(grep -c . "$R/$TAG-sync.txt") (last: $(tail -1 "$R/$TAG-sync.txt" | sed 's/.*(\([0-9]* inserted so far\)).*/\1/')), table lines $(grep -c . "$R/$TAG-table.txt"), skip lines $(grep -c . "$R/$TAG-skip.txt" 2> /dev/null), compaction lines $(grep -c . "$R/$TAG-compaction.txt" 2> /dev/null), devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt")" > "$R/$TAG-summary.txt"
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
grep -q "^exp 0323 | ver run" "$LOCK" 2> /dev/null && : > "$LOCK" && echo "BOX-LOCK released"
