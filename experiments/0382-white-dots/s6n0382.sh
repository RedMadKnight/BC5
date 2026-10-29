#!/usr/bin/env bash
# BC5 experiment 0382 (after exp 0378's s6n0378.sh): one white-dots bench arm of the second title. The shared normal
# build (md5 pinned) through a private copy of play-pkg.sh (own log, working directory, save directory, learned-file
# copy; the shared file is only read). The route save is a FRESH snapshot of the maintainer's live saves taken at the
# arm's start (his current progress, the top session's ask), copied into the private wd; the live saves themselves
# are compared only, never written. Route: slot 4 from the save-slot list (cross at 90 s, down x3, cross, cross;
# exp 0305's slot4-90.cmd), then the scene idles with the camera where the save left it. Screenshots by exp 0190's
# shots.sh into one directory per phase, so every phase is measured on its own (Codex review REVIEW-03, R3/R5); the
# shots stay on the box, only their numbers (exp 0299's wh0299.py, this experiment's dots0382.py, ROI from the
# environment) are kept.
#   MODE=run    (default) phase run: every 10 s from 200 s to 300 s, plus a 1-s burst 281-285.
#   MODE=pause  run, then options at 310 s (paused: 320, 330, 340), options at 350 s (after: 360, 370, 380).
#   MODE=acs    A -> C -> A in one scene: run (A), "rt off" at 310 s and 30 s to settle (c: 340-370 every 10 s),
#               "rt on" at 380 s and 30 s to settle (a2: 410-440). Needs a binary with patch0382-input-rt.diff's "rt"
#               input verb (BC5_0382_BIN, BC5_0382_WANT); the play log's "ray tracing off/on at the flip" lines are
#               checked.
# Arms (the top session's GO): A1 RT on, the defaults, MODE=pause; C RT off; B as an ablation after the map run:
# BVH_MISS per variant (the title's own miss result) before SKIP_PGM (no neutral output, README).
# usage: [MODE=run|pause|acs] [BC5_0382_SWITCHES="..."] [ROI=x0,y0,x1,y1] s6n0382.sh <live-saves sum> <tag> [secs] [on|off]
set -u
EXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:-400}; RT=${4:-on}
case "$RT" in off | on) ;; *) echo "RT is off or on"; exit 1 ;; esac
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
E=$HOME/bc5-work/exp0382; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E30=$W/exp0330
BIN=${BC5_0382_BIN:-$W/kytyplus-build/src/kyty_emulator}; WANT=${BC5_0382_WANT:-58c4a627}   # the shared normal build as read on 2026-10-29 23:5x
SWITCHES=${BC5_0382_SWITCHES-}
MODE=${MODE:-run}
case "$MODE" in run | pause | acs) ;; *) echo "MODE is run, pause or acs"; exit 1 ;; esac
[ "$MODE" = acs ] && [ "$RT" = off ] && { echo "MODE=acs starts with RT on"; exit 1; }
[ "$MODE" = acs ] && [ -z "${BC5_0382_BIN:-}" ] && { echo "MODE=acs needs BC5_0382_BIN (a build with the rt input verb)"; exit 1; }
PH_run="200 210 220 230 240 250 260 270 280 281 282 283 284 285 290 300"
PH_paused="320 330 340"; PH_after="360 370 380"
PH_c="340 350 360 370"; PH_a2="410 420 430 440"
case "$MODE" in run) PHASES="run" ;; pause) PHASES="run paused after" ;; acs) PHASES="run c a2" ;; esac
case "$MODE" in run) NEED=310 ;; pause) NEED=390 ;; acs) NEED=450 ;; esac
[ "$SECS" -ge "$NEED" ] || { echo "MODE=$MODE needs at least $NEED s"; exit 1; }
SD=$W/_SaveData/PPSA03671
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0382.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
ME="white-dots exp 0382 | arm $TAG"
mkdir -p "$R"
[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && grep -qv "^white-dots exp 0382 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 $WANT: not started"; exit 1; }
[ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0305/slot4-90.cmd" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] && [ -x "$W/exp0190/shots.sh" ] && [ -f "$W/exp0299/wh0299.py" ] && [ -f "$E/dots0382.py" ] || { echo "no $LAUNCH_SRC, slot4-90.cmd, sample0330.sh, $LEARN_SRC, shots.sh, wh0299.py or dots0382.py"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
# 1. The private input configuration (RT off or on) and the private learned file.
CFG_SRC=$W/input.cfg; CFG=$E/input-rt$RT.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=$RT"; } > "$CFG" || exit 1
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# 2. The derived launcher: exp 0378's four changed lines and one added line, checked by anchor and by diff size.
PLAY_PKG_MD5=${PLAY_PKG_MD5:-55531ab6}   # play-pkg.sh as read on 2026-10-29 23:5x
[ "$(md5sum < "$LAUNCH_SRC" | cut -c1-8)" = "$PLAY_PKG_MD5" ] || { echo "$LAUNCH_SRC is md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8), not $PLAY_PKG_MD5: not started"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0382/play-last.log  \# exp 0382: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0382/wd  \# exp 0382: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0382/wd/_SaveData-pkg-play  \# exp 0382: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0382/direct-learned-pkg.txt  \# exp 0382: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0382_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0382_INPUT_CONFIG  # exp 0382' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0382.diff"
for h in BC5_0382_INPUT_CONFIG 'exp0382/wd' 'exp0382/play-last.log' 'exp0382/direct-learned-pkg.txt'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0382.diff")" = 9 ] || { echo "the derived launcher's diff is not 4 lines changed + 1 added: not started"; exit 1; }
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
chmod +x "$LAUNCH"
eval "LOG=$(sed -n 's/^LOG=\([^ ]*\).*$/\1/p' "$LAUNCH" | head -1)"
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$E"/*) ;; *) echo "the save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the log $LOG is not under $E: not started"; exit 1 ;; esac
# 3. The private working directory: exp 0330's layout, its symlinks into ~/bc5-work copied as they are.
WD=$E/wd; WD30=$E30/wd; [ -d "$WD30" ] || { echo "no $WD30 to take the layout from: not started"; exit 1; }
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied: not started"; exit 1; }
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] || { echo "$WD/_SaveData or $SDD is not a private directory: not started"; exit 1; }
SROOT=$WD/_SaveData
# 4. The route save: a fresh snapshot of the live saves (his current progress), checked equal, then copied into the wd.
SNAP=$E/saves-$TAG-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') $TAG live saves $WANT_SAVES, snapshot $SNAP (the route save)" | tee -a "$R/s6n-saves.txt"
[ -e "$LOCK" ] || touch "$LOCK"
echo "$ME | white dots, slot 4 RT $RT, ${SECS} s, switches [${SWITCHES:-none}] mode $MODE | $(date '+%F %T')" >> "$LOCK"
EP=""; SP=""; SHP=()
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$SP" ] && kill "$SP" 2> /dev/null; for p in "${SHP[@]}"; do kill "$p" 2> /dev/null; done
  sed -i "/^white-dots exp 0382 | arm $TAG /d" "$LOCK" 2> /dev/null
}
trap cleanup EXIT
trap 'echo "$(date "+%F %T") $TAG aborted" >> "$R/s6n-saves.txt"; exit 1' HUP INT TERM
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
ENDED=""; ROUTED=""; RTOFF=""
ENVS=(BC5_EMU="$BIN" BC5_0382_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd")
[ "$RT" = off ] && ENVS+=(KYTY_BC5_RT=0)
# shellcheck disable=SC2206
ENVS+=($SWITCHES)
# shellcheck disable=SC2206
WANTENV=("BC5_DIRECT_RING_DEPS=dcb" $SWITCHES "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN")
case " $SWITCHES " in *" BC5_DIRECT_SKIP_PGM="*) ;; *) WANTENV+=("BC5_DIRECT_SKIP_PGM=0") ;; esac  # the launcher's default: nothing skipped
case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "refusing to clear $SROOT"; exit 1 ;; esac
cp -a "$SNAP" "$SROOT/PPSA03671" && diff -rq "$SNAP" "$SROOT/PPSA03671" > /dev/null || { echo "the route saves could not be put into $SROOT"; exit 1; }
# The input: exp 0305's slot-4 path, then by MODE (times from the start): pause = options at 310 s and 350 s;
# acs = "rt off" at 310 s and "rt on" at 380 s.
cp "$W/exp0305/slot4-90.cmd" "$E/in-$TAG.cmd"
ms=$(awk '/^wait / {s += $2} END {print s + 0}' "$E/in-$TAG.cmd")
case "$MODE" in
  pause) printf 'wait %d\npress options\nwait 40000\npress options\n' $((310000 - ms)) >> "$E/in-$TAG.cmd" ;;
  acs) printf 'wait %d\nrt off\nwait 70000\nrt on\n' $((310000 - ms)) >> "$E/in-$TAG.cmd" ;;
esac
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG, $SECS s, RT $RT, mode $MODE (phases $PHASES), ROI ${ROI:-whole shot}, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT; env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; cat "$E/in-$TAG.cmd" | tr '\n' ';'; echo; } > "$R/$TAG-start.txt"
"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
for p in $PHASES; do
  v="PH_$p"; mkdir -p "$E/shots-$TAG/$p"; echo "phase $p shots at ${!v}" >> "$R/$TAG-start.txt"
  setsid nohup "$W/exp0190/shots.sh" "$E/shots-$TAG/$p" ${!v} < /dev/null > /dev/null 2>&1 & SHP+=($!)
done
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
T0=$(date +%s)
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|BC5_DIRECT_LEARNED|BC5_DIRECT_SKIP_PGM|BC5_DIRECT_RING_DEPS)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
  [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${WANTENV[@]}"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
fi
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  if [ -z "$RTOFF" ] && [ $(($(date +%s) - T0)) -ge 180 ]; then
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
  sleep 5
done
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""; for p in "${SHP[@]}"; do kill "$p" 2> /dev/null; done; SHP=()
echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
NRT=0; FL=0; SPAN=0; FPS=0
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  nice -n 19 grep -a "timeout probe\|TIMEOUT" "$J" > "$R/$TAG-probe.txt"
  NRT=$(nice -n 19 grep -a -c "ray tracing off:" "$J")
  nice -n 19 grep -a "skip pgm\|ray tracing off:" "$J" | sed 's/(.*so far)//' | awk '{$1 = $1; print}' | sed 's/^[^:]*: //' | sort | uniq -c | sort -rn | head -30 > "$R/$TAG-drops.txt"
  nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/^timing: t \([0-9.]*\) s.*/\1/p' | awk '{b = int($1 / 10) * 10; n[b]++} END {for (k in n) printf "%d %d\n", k, n[k]}' | sort -n > "$R/$TAG-flips-per-10s.txt"
  read -r FL SPAN <<< "$(nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/.*t \([0-9.]*\) s.*/\1/p' | awk 'NR == 1 {a = $1} {b = $1; n++} END {printf "%d %.1f\n", n, b - a}')"
  FPS=$(awk -v n="${FL:-0}" -v s="${SPAN:-0}" 'BEGIN {if (s > 0) printf "%.1f", n / s; else printf "0"}')
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-drops.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
# 5. The shots' numbers, on the box (the shots never leave it).
for p in $PHASES; do   # one set of numbers per phase (Codex review REVIEW-03, R3/R5)
  nice -n 5 distrobox enter ubuntu -- python3 -I "$W/exp0299/wh0299.py" "$E/shots-$TAG/$p" 2>&1 | grep -v "^Container\|OK \]" > "$R/$TAG-$p-wh.txt"
  nice -n 5 distrobox enter ubuntu -- env ROI="${ROI:-}" python3 -I "$E/dots0382.py" "$E/shots-$TAG/$p" 2>&1 | grep -v "^Container\|OK \]" > "$R/$TAG-$p-dots.txt"
done
# MODE=acs: the switch took effect at a flip, both ways (the host's stderr line, bc5LleAgc.cpp ApplyPendingRayTracing)
[ "$MODE" = acs ] && grep -a "input-cmd: ray tracing\|bc5-direct: ray tracing o[nf]*f* at the flip" "$R/$TAG-play.log" > "$R/$TAG-rtswitch.txt"
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; shots $(find "$E/shots-$TAG" -name "*.png" 2> /dev/null | wc -l) in phases $PHASES" > "$R/$TAG-summary.txt"
case "$ENDED" in
  "") if [ "$NC" = 0 ]; then echo pass; else echo "CRASH: $NC crash lines"; fi ;;
  *) echo "$ENDED" ;;
esac > "$R/$TAG-verdict.txt"
sync
cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"; head -8 "$R/$TAG-drops.txt"; for p in $PHASES; do grep -H "^# median" "$R/$TAG-$p-wh.txt" "$R/$TAG-$p-dots.txt"; done; [ "$MODE" = acs ] && cat "$R/$TAG-rtswitch.txt"
S1=$(saves); echo "$(date '+%F %T') $TAG live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot $SNAP): tell the top session before anything is restored"
sync
