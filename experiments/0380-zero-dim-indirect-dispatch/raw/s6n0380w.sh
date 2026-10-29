#!/usr/bin/env bash
# BC5 experiment  0380 (s6n0378.sh by mk-s6n0380.pl; the rebase fix runs) (exp 0372's s6n0372.sh, made by mk-s6n0378.pl): the healthy-frame register baseline of the
# second title. The S6N route RT on with the SHARED normal build (~/bc5-work/kytyplus-build/src/kyty_emulator, md5
# pinned) through a private copy of play-pkg.sh (own log, wd, save directory, learned-file copy; the shared file is
# only read), exp 0196's route save copy in the private wd, the live saves compared only. While the scene runs the
# script asks the installed stall sampler (0377, registers only) for forced samples: `echo once` into its force file,
# 20 samples 5 s apart from t 180 s and 20 more from t 450 s. No wave request is ever written (F520).
# Everything else as s6n0372.sh / s6n0368.sh / s6n0350.sh: exp 0330's memory sampler, fdinfo, flips, the summary.
# usage: s6n0378.sh <expected live-saves sum> <tag> [secs] [off|on]   (on the box; 600 s, RT on by default)
set -u
EXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:-600}; RT=${4:-on}; VARIANT=normal
case "$RT" in off | on) ;; *) echo "RT is off or on"; exit 1 ;; esac
E=$HOME/bc5-work/exp0380w/run; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E30=$W/exp0330
BIN=$W/exp0380w/kyty_emulator; WANT=${BC5_0380_WANT:-c3c8660b}   # exp 0380w: the shared objects + archive eff535ac (link0380r.py), no zero skip
SWITCHES=${BC5_0368_SWITCHES-}
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0380s.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
mkdir -p "$R"
[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^top exp 0380 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?} (build0358.sh first): not started"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0330.sh or $LEARN_SRC"; exit 1; }
FORCE=$HOME/bc5-data/captures/gpu-stall/force; NF=40; LASTF=-10   # exp 0380: no forced requests   # exp 0378: the stall sampler's request file
systemctl is-active -q bc5-gpu-stall-sampler && grep -q '^VERSION = "0377"' /usr/local/sbin/bc5-gpu-stall-sampler && [ -w "$(dirname "$FORCE")" ] || { echo "the stall sampler 0377 is not running or its force directory is not writable: not started"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started"; exit 1; }
# The box's memory settings, read only (the maintainer's to change)
{ echo "swappiness $(cat /proc/sys/vm/swappiness) vfs_cache_pressure $(cat /proc/sys/vm/vfs_cache_pressure) watermark_scale_factor $(cat /proc/sys/vm/watermark_scale_factor) min_free_kbytes $(cat /proc/sys/vm/min_free_kbytes) page-cluster $(cat /proc/sys/vm/page-cluster)"
  echo "zram0 disksize $(cat /sys/block/zram0/disksize 2> /dev/null) comp $(cat /sys/block/zram0/comp_algorithm 2> /dev/null); MemTotal $(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo) MiB; GTT total $(awk '{print int($1/1048576)}' /sys/class/drm/card1/device/mem_info_gtt_total 2> /dev/null) MiB"
  echo "kernel $(uname -r); launcher $LAUNCH_SRC md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8); shared normal $(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8), lean $(md5sum < "$W/kytyplus-build-lean/src/kyty_emulator" | cut -c1-8); private $VARIANT $BIN md5 $WANT; shared bc5-mount $(md5sum < "$W/bc5-tools-ubuntu/release/bc5-mount" 2> /dev/null | cut -c1-8)"
  echo "learned file $LEARN_SRC md5 $(md5sum < "$LEARN_SRC" | cut -c1-8), $(grep -c . "$LEARN_SRC") windows"; } > "$R/$TAG-box-settings.txt"
cat "$R/$TAG-box-settings.txt"
# 1. The private input configuration (RT off or on for this title) and the private learned file.
CFG_SRC=$W/input.cfg; CFG=$E/input-rt$RT.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=$RT"; } > "$CFG" || exit 1
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# exp 0364: BC5_0368_RESET_LEARNED=1 drops the learned windows inside the title's 0x11 window from the PRIVATE copy, so
# the runs meet those regions as a fresh box would (the shared file is only read).
if [ -n "${BC5_0368_RESET_LEARNED:-}" ]; then grep -v '^0x11' "$LEARN" > "$LEARN.tmp" && mv "$LEARN.tmp" "$LEARN"; echo "learned list reset: $(grep -c . "$LEARN") windows kept of $(grep -c . "$LEARN_SRC")"; fi
# 2. The derived launcher: play-pkg.sh with its own log, working directory and save directory, and two hooks after the
#    env-file loop (the input configuration, the learned file).
PLAY_PKG_MD5=${PLAY_PKG_MD5:-55531ab6}   # exp 0378: play-pkg.sh as read on 2026-10-29 10:40
[ "$(md5sum < "$LAUNCH_SRC" | cut -c1-8)" = "$PLAY_PKG_MD5" ] || { echo "$LAUNCH_SRC is md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8), not ${PLAY_PKG_MD5:-?} (int0350.sh's): check the edits below against it, not started (PLAY_PKG_MD5=... to accept)"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
chk 'export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all  # exp 0342 (F412, F415): one ring - every compute buffer on the GFX ring (was 0)'
chk 'export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0380w/run/play-last.log  \# exp 0350/0364: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0380w/run/wd  \# exp 0350/0364: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0380w/run/wd/_SaveData-pkg-play  \# exp 0350/0364: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0380w/run/direct-learned-pkg.txt  \# exp 0350/0364: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0358_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0358_INPUT_CONFIG  # exp 0339' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0380s.diff"
for h in BC5_0358_INPUT_CONFIG 'exp0380w/run/wd' 'exp0380w/run/play-last.log' 'exp0380w/run/direct-learned-pkg.txt' 'COMPUTE_RING=-1'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0380s.diff")" = 9 ] || { echo "the derived launcher's diff is not 4 lines changed + 1 added: not started"; exit 1; }
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
chmod +x "$LAUNCH"
eval "LOG=$(sed -n 's/^LOG=\([^ ]*\).*$/\1/p' "$LAUNCH" | head -1)"
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$E"/*) ;; *) echo "the save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the log $LOG is not under $E: not started"; exit 1 ;; esac
# 3. The private working directory: exp 0330's layout, its symlinks into ~/bc5-work copied as they are. Its _SaveData and
#    save directory are new, empty directories here (exp 0330's wd links the save directory to the shared, empty
#    ~/bc5-work/_SaveData-pkg-play). A later run reuses the directory the first one made.
WD=$E/wd; WD30=$E30/wd; [ -d "$WD30" ] || { echo "no $WD30 to take the layout from: not started"; exit 1; }
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied: not started"; exit 1; }
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] || { echo "$WD/_SaveData or $SDD is not a private directory: not started"; exit 1; }
[ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)" = "$(find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play | wc -l)" ] || { echo "the wd link count differs from $WD30: not started"; exit 1; }
[ -z "$(find "$WD30" -mindepth 1 -maxdepth 1 ! -type l ! -name _SaveData ! -name _SaveData-pkg-play)" ] || { echo "$WD30 has entries that are not links: not started"; exit 1; }
SROOT=$WD/_SaveData
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
echo "launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) ($R/play-pkg-0380s.diff); wd $WD ($(ls -A "$WD" | wc -l) entries)"
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only)" | tee -a "$R/s6n-saves.txt"
echo "top exp 0380 | wb run, scripted route RT $RT, ~10 min ($TAG, private exp0380w $WANT, $SWITCHES) | $(date '+%F %T')" > "$LOCK"
trap '[ -z "${SOAK:-}" ] && grep -q "^top exp 0380 | wb run" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT  # exp 0368: under the soak the loop owns the lock
EP=""; SP=""
abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; [ -n "$SP" ] && kill "$SP" 2> /dev/null; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
ENDED=""; FAIL=""; HANG=""; CRASH=""; DOWN=""; ROUTED=""; RTOFF=""; FL=0; SPAN=0; FPS=0; FDINFO=""
ENVS=(BC5_EMU="$BIN" BC5_0358_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd")
[ "$RT" = off ] && ENVS+=(KYTY_BC5_RT=0)
# shellcheck disable=SC2206
ENVS+=($SWITCHES)
WANTENV=("BC5_DIRECT_COMPUTE_RING=-1" "BC5_DIRECT_RING_DEPS=dcb" "BC5_DIRECT_GPU_CHECK=1" "BC5_DIRECT_GPU_CHECK_PRODUCT=1" "BC5_DIRECT_SHADOW_LABELS=1" "BC5_DIRECT_HOST_INDIRECT=learn:1100000000" "BC5_DIRECT_SOFT_WAIT_MS=8" $SWITCHES "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN")
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
  echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_LAZY_NAMES|BC5_DIRECT_EAGER_NAMES|BC5_DIRECT_LEARNED|BC5_DIRECT_JOURNAL|BC5_DIRECT_JOURNAL_DONTNEED|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_BREAKDOWN_NODATA|BC5_IMPORT_LOG|BC5_DIRECT_SKIP_PGM|MALLOC_ARENA_MAX|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
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
  if [ -z "$FDINFO" ] && [ $(($(date +%s) - T0)) -ge 120 ]; then  # exp 0341: the rings the work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)
    FDINFO=1; { echo "at $(($(date +%s) - T0)) s:"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } > "$R/$TAG-fdinfo.txt"
  fi
  if [ "$VARIANT" = normal ] && [ -z "$RTOFF" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
    J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
    if [ ! -f "$J" ] || [ "$(stat -c %Y "$J")" -lt "$T0" ]; then ENDED="SETUP: no journal of this run by 180 s"; break
    elif [ "$RT" = off ]; then
      if grep -aq "ray tracing off:" "$J"; then RTOFF=1; else ENDED="SETUP: no RT-off drop line by 180 s: ray tracing is not off"; break; fi
    else
      if grep -aq "ray tracing off:" "$J"; then ENDED="SETUP: an RT-off drop line by 180 s: ray tracing is not on"; break; else RTOFF=on; fi
    fi
  fi
  if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
    sleep 25
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="DOWN: kernel amdgpu line, reset failed or MODE1"
    elif sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, ring reset succeeded"
    else ENDED="HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, no reset line"; fi
    break
  fi
  T=$(($(date +%s) - T0))   # exp 0378: forced register samples, 20 from t 180 s and 20 from t 450 s, >= 5 s apart
  if [ "$NF" -lt 40 ] && [ $((T - LASTF)) -ge 5 ] && { { [ "$T" -ge 180 ] && [ "$NF" -lt 20 ]; } || [ "$T" -ge 450 ]; }; then
    echo once > "$FORCE" && NF=$((NF + 1)) && LASTF=$T && echo "$NF $(date '+%T.%3N') t $T" >> "$R/$TAG-forced-times.txt"
  fi
  sleep 5
done
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then { echo "at $DUR s (end):"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } >> "$R/$TAG-fdinfo.txt"; fi
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""
echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
{ grep -a "experiment 0341 switches\|experiment 0341 at close\|experiment 0346 at close\|experiment 0349\|experiment 0352\|thread trap|amm fault|amm ledger|no pending map\|amm ledger\|no pending map\|cs refused" "$R/$TAG-play.log"; grep -a "experiment 0341 periodic" "$R/$TAG-play.log" | tail -1; grep -a "args histogram" "$R/$TAG-play.log" | tail -2; echo "bo lines: $(grep -a -c 'bc5-direct: bo ' "$R/$TAG-play.log") (userptr map $(grep -a -c 'bo userptr map' "$R/$TAG-play.log"), unmap $(grep -a -c 'bo userptr unmap' "$R/$TAG-play.log"), shared map $(grep -a -c 'bo shared map' "$R/$TAG-play.log"), scratch $(grep -a -c 'bo scratch slot' "$R/$TAG-play.log"))"; grep -a 'bc5-direct: bo ' "$R/$TAG-play.log" | grep -v 'userptr\|shared' | head -20; } > "$R/$TAG-0341.txt" 2> /dev/null   # exp 0341: the backend's lines
{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
NRT=0; NCR=0
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  grep -a "^frame profile" "$J" | awk '{g=0;fl=0;p=0;s=0; for(i=1;i<=NF;i++){ if($i=="busy") g=$(i+1); if($i=="filter") fl=$(i+1); if($i=="prepare" && $(i+1)!="=") p=$(i+1); if($i=="ms" && $(i+1)=="since") s=$(i-1)} G+=g; FL+=fl; P+=p; S+=s; n++} END {if (n>0) printf "exp 0358 frame profiles %d: per frame GPU busy %.2f ms, host prepare %.2f ms (filter %.2f), %.1f ms between flips\n", n, G/n, P/n, FL/n, S/n}' > "$R/$TAG-0358.txt"
  nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
  NRT=$(nice -n 19 grep -a -c "ray tracing off:" "$J")
  nice -n 19 grep -a "^learned 0x\|^hint \|direct memory +\|^learned: fault\|^scratch: window" "$J" > "$R/$TAG-forced.txt"
  nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | tail -1 > "$R/$TAG-pinned.txt"
  nice -n 19 grep -a "compute ring:" "$J" | head -50 > "$R/$TAG-compute-ring.txt"; NCR=$(nice -n 19 grep -a -c "compute ring:" "$J")
  nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/^timing: t \([0-9.]*\) s.*/\1/p' | awk '{b = int($1 / 10) * 10; n[b]++} END {for (k in n) printf "%d %d\n", k, n[k]}' | sort -n > "$R/$TAG-flips-per-10s.txt"
  read -r FL SPAN <<< "$(nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/.*t \([0-9.]*\) s.*/\1/p' | awk 'NR == 1 {a = $1} {b = $1; n++} END {printf "%d %.1f\n", n, b - a}')"
  FPS=$(awk -v n="${FL:-0}" -v s="${SPAN:-0}" 'BEGIN {if (s > 0) printf "%.1f", n / s; else printf "0"}')
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
find "$(dirname "$FORCE")" -maxdepth 1 -mindepth 1 -type d -newermt "@$T0" -printf '%f\n' | sort > "$R/$TAG-sampler-dirs.txt"   # exp 0378
awk -v t="$(date -d "@$T0" '+%FT%T')" '$1 >= t' "$(dirname "$FORCE")/stalls.log" > "$R/$TAG-stalls-log.txt"
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
cmp -s "$LEARN_SRC" "$LEARN" && echo "the private learned file is unchanged" > "$R/$TAG-learned.txt" || diff "$LEARN_SRC" "$LEARN" > "$R/$TAG-learned.txt"
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
sleep 2
X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${X:-no launcher exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, compute-ring lines $NCR, fdinfo engines $(grep -a -o 'drm-engine-[a-z]*' "$R/$TAG-fdinfo.txt" 2> /dev/null | sort -u | tr '\n' ' '), devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; $(cut -c1-120 "$R/$TAG-pinned.txt" 2> /dev/null); imports $(grep -c "	" "$R/$TAG-imports.txt" 2> /dev/null) (stubs $(grep -c "	stub$" "$R/$TAG-imports.txt" 2> /dev/null)), call lines $(grep -c " call " "$R/$TAG-imports.txt" 2> /dev/null), procparam $(grep -c "procparam" "$R/$TAG-imports.txt" 2> /dev/null); $(head -1 "$R/$TAG-learned.txt")" > "$R/$TAG-summary.txt"
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
cat "$R/$TAG-summary.txt" "$R/$TAG-0358.txt" "$R/$TAG-verdict.txt"
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot $SNAP): tell the maintainer before anything is restored"
sync
grep -q "^top exp 0380 | wb run" "$LOCK" 2> /dev/null && : > "$LOCK" && echo "BOX-LOCK released"
