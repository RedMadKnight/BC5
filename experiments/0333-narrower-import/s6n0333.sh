#!/usr/bin/env bash
# BC5 experiment 0333, arm S1: where the all-zero chunks of the two render heaps lie, scan after scan, on S6N's route with
# RT off. Exp 0330's chain (s6n0330.sh: a derived launcher with a private working directory, its own _SaveData and log and
# a private input configuration with RT off; the live saves compared only, never written) with exp 0333's private binary
# (patch0333.py: the zero scan at a list of times and the zero map; diagnostic, nothing released) and one run:
#   S1  BC5_DIRECT_BREAKDOWN_AT=230 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=240,480,720,960,1180
#       BC5_DIRECT_ZEROSCAN_MAP=RenderGpuWcLarge,CommitIABufferAllocator; learned faults go to a private copy of the shared
#       learned file (exp0333/direct-learned-pkg.txt), so the run cannot change what the maintainer's play imports.
# The run: the box's memory every 10 s (exp 0330's sample0330.sh), the journal's breakdown, zero-scan and zero-map lines,
# its learned and hint import lines, flips per 10 s, RT-off drop lines, crash and kernel lines. It stops on a kernel
# amdgpu line, a live-save change, or a run that is not what it claims (binary, private directories, route, RT off, the
# environment).
# usage: s6n0333.sh <expected live-saves sum> [secs]   (on the box; secs at most 1,260, 1,200 by default)
set -u
EXPECT_SAVES=${1:?the live saves sum}; SECS=${2:-1200}
E=$HOME/bc5-work/exp0333; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E30=$W/exp0330
BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2> /dev/null)   # run0333.sh build writes it
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0333.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
ZS_AT=240,480,720,960,1180; ZS_MAP=RenderGpuWcLarge,CommitIABufferAllocator
mkdir -p "$R"
[ "$SECS" -le 1260 ] || { echo "at most 1,260 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?} (run0333.sh build first): not started"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0330.sh or $LEARN_SRC"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started"; exit 1; }
# The box's memory settings, read only (the maintainer's to change)
{ echo "swappiness $(cat /proc/sys/vm/swappiness) vfs_cache_pressure $(cat /proc/sys/vm/vfs_cache_pressure) watermark_scale_factor $(cat /proc/sys/vm/watermark_scale_factor) min_free_kbytes $(cat /proc/sys/vm/min_free_kbytes) page-cluster $(cat /proc/sys/vm/page-cluster)"
  echo "zram0 disksize $(cat /sys/block/zram0/disksize 2> /dev/null) comp $(cat /sys/block/zram0/comp_algorithm 2> /dev/null); MemTotal $(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo) MiB; GTT total $(awk '{print int($1/1048576)}' /sys/class/drm/card1/device/mem_info_gtt_total 2> /dev/null) MiB"
  echo "kernel $(uname -r); launcher $LAUNCH_SRC md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8); shared normal $(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8); private $BIN md5 $WANT; shared bc5-mount $(md5sum < "$W/bc5-tools-ubuntu/release/bc5-mount" 2> /dev/null | cut -c1-8)"
  echo "learned file $LEARN_SRC md5 $(md5sum < "$LEARN_SRC" | cut -c1-8), $(grep -c . "$LEARN_SRC") windows"; } > "$R/box-settings.txt"
cat "$R/box-settings.txt"
# 1. The private input configuration (RT off for this title) and the private learned file.
CFG_SRC=$W/input.cfg; CFG=$E/input-rtoff.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=off"; } > "$CFG" || exit 1
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# 2. The derived launcher: play-pkg.sh with its own log, working directory and save directory, and two hooks after the
#    env-file loop (the input configuration, the learned file).
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0333/play-last.log  \# exp 0333: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0333/wd  \# exp 0333: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0333/wd/_SaveData-pkg-play  \# exp 0333: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0333/direct-learned-pkg.txt  \# exp 0333: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0333_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0333_INPUT_CONFIG  # exp 0333' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0333.diff"
for h in BC5_0333_INPUT_CONFIG 'exp0333/wd' 'exp0333/play-last.log' 'exp0333/direct-learned-pkg.txt'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0333.diff")" = 9 ] || { echo "the derived launcher's diff is not 4 lines changed + 1 added: not started"; exit 1; }
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
chmod +x "$LAUNCH"
eval "LOG=$(sed -n 's/^LOG=\([^ ]*\).*$/\1/p' "$LAUNCH" | head -1)"
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$E"/*) ;; *) echo "the save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the log $LOG is not under $E: not started"; exit 1 ;; esac
# 3. The private working directory: exp 0330's layout, its symlinks into ~/bc5-work copied as they are. Its _SaveData and
#    save directory are new, empty directories here (exp 0330's wd links the save directory to the shared, empty
#    ~/bc5-work/_SaveData-pkg-play).
WD=$E/wd; WD30=$E30/wd; [ -d "$WD30" ] || { echo "no $WD30 to take the layout from: not started"; exit 1; }
[ -e "$WD" ] && { echo "$WD exists: not started"; exit 1; }
mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied: not started"; exit 1; }
[ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)" = "$(find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play | wc -l)" ] || { echo "the wd link count differs from $WD30: not started"; exit 1; }
[ -z "$(find "$WD30" -mindepth 1 -maxdepth 1 ! -type l ! -name _SaveData ! -name _SaveData-pkg-play)" ] || { echo "$WD30 has entries that are not links: not started"; exit 1; }
SROOT=$WD/_SaveData
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
echo "launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) ($R/play-pkg-0333.diff); wd $WD ($(ls -A "$WD" | wc -l) entries)"
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only)" | tee -a "$R/s6n-saves.txt"
echo "cloud exp 0333 | s6n run: the second title's S6N route, RT off, the zero map (arm S1), $SECS s, exp0333 binary, private wd | start $(date +%H:%M) | until ~$(date -d "+$(((SECS + 90) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0333 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
EP=""; SP=""
abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; [ -n "$SP" ] && kill "$SP" 2> /dev/null; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
TAG=S1; ENDED=""; FAIL=""; HANG=""; CRASH=""; DOWN=""; ROUTED=""; RTOFF=""; FL=0; SPAN=0; FPS=0
ENVS=(BC5_EMU="$BIN" KYTY_BC5_RT=0 BC5_0333_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" BC5_DIRECT_BREAKDOWN_AT=230 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT="$ZS_AT" BC5_DIRECT_ZEROSCAN_MAP="$ZS_MAP")
WANTENV=("BC5_DIRECT_ZEROSCAN_AT=$ZS_AT" "BC5_DIRECT_ZEROSCAN_MAP=$ZS_MAP" "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN")
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "refusing to clear $SROOT"; exit 1 ;; esac
cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "the route saves could not be put into $SROOT"; exit 1; }
find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT; env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; } > "$R/$TAG-start.txt"
"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
T0=$(date +%s)
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_LAZY_NAMES|BC5_DIRECT_EAGER_NAMES|BC5_DIRECT_LEARNED|BC5_DIRECT_JOURNAL|BC5_DIRECT_JOURNAL_DONTNEED|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_BREAKDOWN_NODATA|BC5_DIRECT_ZEROSCAN_AT|BC5_DIRECT_ZEROSCAN_MAP|BC5_DIRECT_SKIP_PGM|MALLOC_ARENA_MAX|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
  [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${WANTENV[@]}"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
fi
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
    if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1
    elif [ "$ATIME_OK" = 1 ]; then ENDED="SETUP: the route save was not read by 60 s"; break
    else ROUTED=warned; fi
  fi
  if [ -z "$RTOFF" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
    J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
    if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ] && grep -aq "ray tracing off:" "$J"; then RTOFF=1
    else ENDED="SETUP: no RT-off drop line by 180 s: ray tracing is not off"; break; fi
  fi
  if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
    sleep 25
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="DOWN: kernel amdgpu line, reset failed or MODE1"
    elif sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, ring reset succeeded"
    else ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, no reset line"; fi
    break
  fi
  sleep 5
done
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""
echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
NRT=0
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
  NRT=$(nice -n 19 grep -a -c "ray tracing off:" "$J")
  nice -n 19 awk '/by name \(at the set time\)/ {p = 1} p {print} p && /total \(views may alias\)/ {p = 0}' "$J" > "$R/$TAG-breakdown.txt"
  nice -n 19 awk '/^zero scan \(exp 0330\)/ {p = 1} p {print} p && /^  total/ {p = 0}' "$J" > "$R/$TAG-zeroscan.txt"
  nice -n 19 grep -a "^zero map" "$J" > "$R/$TAG-zeromap.txt"
  nice -n 19 grep -a "^learned 0x\|^hint \|direct memory +\|^learned: fault\|^scratch: window" "$J" > "$R/$TAG-forced.txt"
  nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | tail -1 > "$R/$TAG-pinned.txt"
  nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/^timing: t \([0-9.]*\) s.*/\1/p' | awk '{b = int($1 / 10) * 10; n[b]++} END {for (k in n) printf "%d %d\n", k, n[k]}' | sort -n > "$R/$TAG-flips-per-10s.txt"
  read -r FL SPAN <<< "$(nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/.*t \([0-9.]*\) s.*/\1/p' | awk 'NR == 1 {a = $1} {b = $1; n++} END {printf "%d %.1f\n", n, b - a}')"
  FPS=$(awk -v n="${FL:-0}" -v s="${SPAN:-0}" 'BEGIN {if (s > 0) printf "%.1f", n / s; else printf "0"}')
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
cmp -s "$LEARN_SRC" "$LEARN" && echo "the private learned file is unchanged" > "$R/$TAG-learned.txt" || diff "$LEARN_SRC" "$LEARN" > "$R/$TAG-learned.txt"
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
sleep 2
X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${X:-no launcher exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; $(cut -c1-120 "$R/$TAG-pinned.txt" 2> /dev/null); zero scans $(grep -c '^  total' "$R/$TAG-zeroscan.txt" 2> /dev/null), zero-map lines $(grep -c . "$R/$TAG-zeromap.txt" 2> /dev/null); $(head -1 "$R/$TAG-learned.txt")" > "$R/$TAG-summary.txt"
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
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot $SNAP): tell the maintainer before anything is restored"
sync
grep -q "^cloud exp 0333 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
