#!/usr/bin/env bash
# BC5 experiment 0227: one run of the load-time A/B. Arms:
#   RA0  the shared build, KYTY_BC5_APR_READAHEAD=0 (the read path before exp 0203; the launchers' default since
#        2026-10-22 23:59);
#   RA4  the shared build, KYTY_BC5_APR_READAHEAD=4 (the read-ahead as it was on by default 20:03-23:59, the regression);
#   FIX  ~/bc5-work/exp0227/kyty_emulator (patch_0227.diff: readers leave large buffers and parallel runs to the
#        worker), KYTY_BC5_APR_READAHEAD=4;
#   OLD  ~/bc5-work/exp0214/kyty_emulator.before-0214, the shared build of 10:22 before any read-ahead code;
#   CUR  the shared build with nothing set: the launcher's own default (read-ahead off since 2026-10-22 23:59).
# Each run also records the box's state at its start and end (MemAvailable, PSI memory/io totals, vmstat compact_stall,
# pswpin, pswpout, pgmajfault), so that box state can be told apart from code (the box thrashed on 2026-10-22).
# Titles:
#   astro  ASTRO BOT through a copy of play-astro.sh with a BC5_EMU line (play-astro-0227.sh). The route is
#          astro-route.sh's start: its saves (save-backup-astro), cross at 50 s on the title, cross 25 s later to load
#          the save into the level. The LIVE saves are kept aside first and put back after (diff -rq).
#   pkg    the second title through play-pkg.sh (BC5_EMU for FIX), exp 0203's O2 route (saves-before-152617,
#          o2-continue.cmd: Continue at 85 s, then the save loads), saves by exp 0196's ab-restore.sh.
# Beside each run: io0227.sh (the process's read counters every 0.5 s), exp 0220's mem0220.sh. Only the emulator PID
# this run started is stopped. Only on the top session's Go; inside chain0227.sh the chain's lock line is reused.
# usage: run0227.sh <astro|pkg> <tag> <RA0|RA4|FIX> <secs>   (on the box)
set -u
TITLE=${1:?astro or pkg}; TAG=${2:?tag}; ARM=${3:?RA0, RA4 or FIX}; SECS=${4:-150}
E=$HOME/bc5-work/exp0227; R=$E/raw; W=$HOME/bc5-work
LOCK=$W/BOX-LOCK
mkdir -p "$R"
[ "$SECS" -le 600 ] || { echo "at most 600 s"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used in $R"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0227 |" "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
case $ARM in
  RA0) AENV="KYTY_BC5_APR_READAHEAD=0" ;;
  RA4) AENV="KYTY_BC5_APR_READAHEAD=4" ;;
  FIX) AENV="KYTY_BC5_APR_READAHEAD=4 BC5_EMU=$E/kyty_emulator"; [ -x "$E/kyty_emulator" ] || { echo "no fixed binary"; exit 1; } ;;
  OLD) AENV="KYTY_BC5_APR_READAHEAD=0 BC5_EMU=$E/old/kyty_emulator"  # a symlink to exp0214/kyty_emulator.before-0214, so the process is named kyty_emulator
       [ -x "$E/old/kyty_emulator" ] || { echo "no $E/old/kyty_emulator"; exit 1; } ;;
  CUR) AENV="" ;;  # the shared build with the launcher's own default (KYTY_BC5_APR_READAHEAD=0 since 23:59)
  CH0) AENV="BC5_DIRECT_CHAIN=0" ;;  # the shared build without play-astro.sh's submission chains (its default 2 since 2026-10-22)
  NOCAP) AENV="BC5_RUN_ENV=$E/bc5-run-nocapture.env"  # bc5-run.env with PLAY_CAPTURE=0: no capture dir, no direct journal
         [ -r "$E/bc5-run-nocapture.env" ] || { echo "no $E/bc5-run-nocapture.env"; exit 1; } ;;
  COLD) AENV=""; DROP=1 ;;  # CUR after the page cache is dropped (the cold/warm test of 2026-10-23)
  TRACE) AENV="KYTY_BC5_AMM_TRACE=1" ;;  # CUR with every APR submit and read traced (does ASTRO BOT submit multi-read buffers?)
  PAR8) AENV="KYTY_BC5_APR_PARALLEL=8" ;;  # CUR with exp 0112's 8-way read runs, as the second title's launcher has them
  *) echo "arm RA0, RA4, FIX, OLD, CUR, CH0, NOCAP, COLD, TRACE or PAR8"; exit 1 ;;
esac
boxstate() {  # <label>: one line of the box's memory state and its cumulative pressure counters
  echo "box $1 uptime $(cut -d' ' -f1 /proc/uptime) avail_mib $(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "swapfree_mib $(awk '/^SwapFree:/ {print int($2 / 1024)}' /proc/meminfo)" \
    "$(awk '$1 ~ /^(compact_stall|compact_fail|pswpin|pswpout|pgmajfault)$/ {printf "%s %s ", $1, $2}' /proc/vmstat)" \
    "psi_mem_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/memory)" \
    "psi_io_full_us $(awk '/^full/ {sub("total=", "", $5); print $5}' /proc/pressure/io)"
}
put() {  # <from> <to>: make <to> a copy of <from>, as astro-route.sh's restore does; true when identical
  mkdir -p "$2" && cp -a "$1/." "$2/" || return 1
  local d
  for d in "$2"/*/; do d=${d%/}; [ -e "$d" ] || continue; [ -e "$1/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$1" "$2" > /dev/null
}
if [ "$TITLE" = astro ]; then
  SD=$W/_SaveData/PPSA21564; BK=$W/save-backup-astro; KEEP=$E/astro-live-$TAG
  LAUNCH=$E/play-astro-0227.sh; LOG=$W/play-last.log
  [ -d "$BK" ] && [ -d "$SD" ] && [ -x "$LAUNCH" ] || { echo "no $BK, $SD or $LAUNCH"; exit 1; }
  cp -a "$SD" "$KEEP" && diff -rq "$SD" "$KEEP" > /dev/null || { echo "the live saves were not kept: stop"; exit 1; }
  put "$BK" "$SD" && echo "route saves from $BK in $SD (live saves kept in $KEEP)" | tee "$R/$TAG-restore.txt" \
    || { put "$KEEP" "$SD"; echo "route saves did not go in; live saves put back: stop"; exit 1; }
  printf 'wait 50000\npress cross\nwait 25000\npress cross\n' > "$E/in-$TAG.cmd"
  # The first non-black frame comes from screenshots (shots below): BC5_DIRECT_FLIP_BRIGHT is never reached while
  # BC5_DIRECT_FLIP_DEFER=1 (bc5-run.env), whose branch returns before it (runs AP1-AP4 wrote no line).
  JENV="KYTY_BC5_FPS_COUNTER=1"
else
  SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617; LAUNCH=$W/play-pkg.sh; LOG=$W/play-pkg-last.log
  [ -d "$SAVES" ] || { echo "no $SAVES"; exit 1; }
  sleep 2  # ab-restore.sh names its copies by time
  OUT=$("$W/exp0196/ab-restore.sh" "$SAVES") || { echo "$OUT"; exit 1; }
  echo "$OUT" | tee "$R/$TAG-restore.txt"
  KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
  [ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; exit 1; }
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  JENV="KYTY_BC5_APR_FILE_JOURNAL=7cd713df"
fi
OWN=0
[ -s "$LOCK" ] || { OWN=1; echo "exp 0227 | load-time run $TAG ($TITLE, $ARM, $SECS s) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 3)) min" +%H:%M)" > "$LOCK"; }
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
{ date '+%F %T'; echo "title $TITLE, arm $ARM ($AENV), $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-32)"
  echo "launcher read-ahead line: $(grep -n "KYTY_BC5_APR_READAHEAD" "$LAUNCH" | head -2 | tr '\n' ' ')"
  B=$W/kytyplus-build/src/kyty_emulator; [ "$ARM" = FIX ] && B=$E/kyty_emulator
  [ "$ARM" = OLD ] && B=$E/old/kyty_emulator
  echo "binary $B md5 $(md5sum < "$B" | cut -c1-32)"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"
  echo "before: $(free -m | awk 'NR > 1 {printf "%s used %s free %s avail %s; ", $1, $3, $4, $7}')"
  boxstate start; } > "$R/$TAG-start.txt"
if [ "${DROP:-0}" = 1 ]; then  # a cold page cache (the cold/warm test of 2026-10-23); allowed by /etc/sudoers.d/bc5-claude
  sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches > /dev/null && echo "page cache dropped at uptime $(cut -d' ' -f1 /proc/uptime); $(free -m | awk 'NR == 2 {printf "buff/cache %s MiB, avail %s MiB", $6, $7}')" >> "$R/$TAG-start.txt"
fi
U0=$(cut -d' ' -f1 /proc/uptime)
if [ "$TITLE" = astro ] && [ "${SHOTS:-1}" = 1 ]; then  # back-to-back screenshots of the active window for SHOT_SECS s
  mkdir -p "$E/shots/$TAG"  # (each takes ~4.4 s, spectacle's start); kept on the box (private), scored there by shots0227.py
  ( end=$(($(date +%s) + ${SHOT_SECS:-60})); i=0
    while [ "$(date +%s)" -lt "$end" ]; do
      u=$(cut -d' ' -f1 /proc/uptime)
      XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 timeout 10 spectacle -b -n -a -o "$E/shots/$TAG/s$(printf %03d $i).jpg" > /dev/null 2>&1
      echo "s$(printf %03d $i).jpg $u $(cut -d' ' -f1 /proc/uptime)" >> "$E/shots/$TAG/index.txt"; i=$((i + 1))
    done ) < /dev/null > /dev/null 2>&1 &
fi
# shellcheck disable=SC2086
setsid nohup distrobox enter ubuntu -- env -u BC5_EMU $AENV KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" $JENV "$LAUNCH" \
  < /dev/null > "$R/$TAG-launch.out" 2>&1 &
EP=""
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done  # the process name, by prefix: kyty_emulator.before-0214 ran unseen by -x on 2026-10-23
TK=$(getconf CLK_TCK)
echo "launch at uptime $U0; emulator pid ${EP:-none} started at uptime $(awk -v k="$TK" '{printf "%.2f", $22 / k}' "/proc/${EP:-1}/stat" 2> /dev/null): $(ps -o args= -p "${EP:-1}" 2> /dev/null | cut -c1-100)" >> "$R/$TAG-start.txt"
if [ -n "$EP" ]; then
  # which switches reached the emulator (BC5_DIRECT_FLIP_BRIGHT wrote nothing in runs AP1-AP4)
  echo "environ: $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_DIRECT_FLIP_BRIGHT|BC5_DIRECT_CHAIN|KYTY_BC5_APR_READAHEAD|KYTY_BC5_APR_PARALLEL|PLAY_CAPTURE|BC5_GC_DUMP_DIR|BC5_LOGGING)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
  setsid nohup "$E/io0227.sh" "$R/$TAG-io.txt" "$EP" < /dev/null > /dev/null 2>&1 &
  [ "$TITLE" = astro ] && setsid nohup "$E/bcm0227.sh" "$R/$TAG-bcm.txt" "$EP" < /dev/null > /dev/null 2>&1 &
  setsid nohup nice -n 10 "$W/exp0220/mem0220.sh" "$R/$TAG-mem.txt" "$EP" < /dev/null > /dev/null 2>&1 &
fi
T0=$(date +%s); ENDED=""
[ -n "$EP" ] || ENDED="no emulator started"
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  sleep 1
done
boxstate end > "$R/$TAG-box-end.txt"
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3
echo "$TAG ${ENDED:-stopped at $SECS s}" | tee "$R/$TAG-end.txt"
cp -p "$LOG" "$R/$TAG-play.log"
grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play.log" > "$R/$TAG-crash.txt"
if [ "$TITLE" = astro ]; then  # this run's GPU journal (PLAY_CAPTURE=1 in bc5-run.env): the flip-brightness jumps
  J=$(cat "$W/last-play-capture" 2> /dev/null)/gc/direct.log
  echo "$J $(stat -c '%y %s' "$J" 2> /dev/null)" > "$R/$TAG-journal-path.txt"
  grep -a "^flip bright" "$J" > "$R/$TAG-bright.txt" 2> /dev/null
fi
N=$(cat "$R/$TAG-dmesg-before.txt")
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung" > "$R/$TAG-dmesg-after.txt"
sleep 2
if [ "$TITLE" = astro ]; then
  if put "$KEEP" "$SD"; then echo "live saves back and identical to $KEEP" | tee "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" | tee "$R/$TAG-restore-back.txt"; fi
else
  "$W/exp0196/ab-restore.sh" "$KEEP" | tee "$R/$TAG-restore-back.txt"
  if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then
    echo "NESTED SAVE COPY in $KEEP or $SD: the live saves need checking by hand" | tee -a "$R/$TAG-restore-back.txt"
  elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" | tee -a "$R/$TAG-restore-back.txt"
  else echo "LIVE SAVES DIFFER from $KEEP" | tee -a "$R/$TAG-restore-back.txt"; fi
fi
[ "$OWN" = 1 ] && grep -q "^exp 0227 | load-time run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
echo "$TAG: crash lines $(grep -c . "$R/$TAG-crash.txt"), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), read $(awk '$1 == "i" {r = $3} END {printf "%.0f", r / 1048576}' "$R/$TAG-io.txt") MiB (rchar)" | tee "$R/$TAG-summary.txt"
# the box's state over the run: MemAvailable at both ends, and the counters' deltas
{ grep "^box start" "$R/$TAG-start.txt"; cat "$R/$TAG-box-end.txt"; } | awk -v t="$TAG" '
  {for (i = 3; i < NF; i += 2) v[NR, $i] = $(i + 1)}
  END {printf "%s box: avail %s -> %s MiB; compact_stall +%d (fail +%d), pswpin +%d, pswpout +%d, majfault +%d; PSI full mem %.1f s, io %.1f s\n", t,
       v[1, "avail_mib"], v[2, "avail_mib"], v[2, "compact_stall"] - v[1, "compact_stall"], v[2, "compact_fail"] - v[1, "compact_fail"],
       v[2, "pswpin"] - v[1, "pswpin"], v[2, "pswpout"] - v[1, "pswpout"], v[2, "pgmajfault"] - v[1, "pgmajfault"],
       (v[2, "psi_mem_full_us"] - v[1, "psi_mem_full_us"]) / 1e6, (v[2, "psi_io_full_us"] - v[1, "psi_io_full_us"]) / 1e6}' | tee -a "$R/$TAG-summary.txt"
