#!/usr/bin/env bash
# BC5 experiment 0330: the host's memory, arm by arm, on S6N's route with RT off. Exp 0319's chain (s6n0319.sh: a derived
# launcher with a private working directory, its own _SaveData and log and a private input configuration with RT off;
# the live saves compared only, never written) with exp 0330's private binary (patch0330.py: the timed breakdown, the
# zero scan, the journal's page-cache drop; all off by default) and one run per arm:
#   A  the private binary with BC5_DIRECT_BREAKDOWN_AT=540 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=550
#   B  A + BC5_DIRECT_JOURNAL_DONTNEED=1 (the journal's written pages leave the page cache)
#   C  A + the CPU-only heaps lazy: BC5_DIRECT_LAZY_NAMES = A's list + Wwise,SoundAlloc,FileSystem,UIStringAlloc
#   D  A + KYTY_GUEST_MEMORY_MB=12288 (does the title size its pools smaller? exp 0288 Q2)
# Every run: the box's memory every 10 s (sample0330.sh), the journal's breakdown and zero-scan tables, its learned and
# hint import lines, flips/s, RT-off drop lines, crash and kernel lines. A crash or a recovered hang is recorded and the
# chain goes on (C and D change what the title gets); it stops on the machine-down class, a live-save change, or a run
# that is not what it claims (binary, private directories, route, RT off, the arm's environment).
# usage: s6n0330.sh <expected live-saves sum> [secs] [arms...]   (on the box; arms default to A B C D, C needs A first)
set -u
EXPECT_SAVES=${1:?the live saves sum}; SECS=${2:-600}; shift 2 2> /dev/null || shift $#; ARMS=${*:-A B C D}
E=$HOME/bc5-work/exp0330; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2> /dev/null)   # run0330.sh build writes it
SD=$W/_SaveData/PPSA03671; SAVES=$W/exp0196/saves-before-152617
LAUNCH_SRC=$W/play-pkg.sh; L99=$W/exp0299/play-pkg-0299.sh; LAUNCH=$E/play-pkg-0330.sh
mkdir -p "$R"
[ "$SECS" -le 600 ] || { echo "at most 600 s a run"; exit 1; }
for a in $ARMS; do case "$a" in A | B | C | D) ;; *) echo "unknown arm $a"; exit 1 ;; esac; done
case " $ARMS " in *" C "*) case " $ARMS " in *" A "*" C "*) ;; *) echo "arm C takes its lazy list from arm A's run: put A before C"; exit 1 ;; esac ;; esac
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?} (run0330.sh build first): not started"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] && [ -x "$E/sample0330.sh" ] || { echo "no $SAVES, $LAUNCH_SRC, o2-continue.cmd or sample0330.sh"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started"; exit 1; }
# The box's memory settings, read only (the maintainer's to change)
{ echo "swappiness $(cat /proc/sys/vm/swappiness) vfs_cache_pressure $(cat /proc/sys/vm/vfs_cache_pressure) watermark_scale_factor $(cat /proc/sys/vm/watermark_scale_factor) min_free_kbytes $(cat /proc/sys/vm/min_free_kbytes) page-cluster $(cat /proc/sys/vm/page-cluster)"
  echo "zram0 disksize $(cat /sys/block/zram0/disksize 2> /dev/null) comp $(cat /sys/block/zram0/comp_algorithm 2> /dev/null); MemTotal $(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo) MiB; GTT total $(awk '{print int($1/1048576)}' /sys/class/drm/card1/device/mem_info_gtt_total 2> /dev/null) MiB"
  echo "launcher $LAUNCH_SRC md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8); shared normal $(md5sum < "$W/kytyplus-build/src/kyty_emulator" | cut -c1-8); private $BIN md5 $WANT"; } > "$R/box-settings.txt"
cat "$R/box-settings.txt"
# 1. The private input configuration: RT off for this title.
CFG_SRC=$W/input.cfg; CFG=$E/input-rtoff.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=off"; } > "$CFG" || exit 1
# 2. The derived launcher: play-pkg.sh + exp 0299's edits renamed to 0330, and three hooks after the env-file loop (the
#    input configuration, the lazy list, the guest memory size); a later assignment of either variable takes the hook's
#    value when one is given.
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0330/play-last.log  \# exp 0330: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0330/wd  \# exp 0330: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0330/wd/_SaveData-pkg-play  \# exp 0330: private#' "$LAUNCH" || exit 1
sed -i -E '/\\$/!s/^([[:space:]]*(export[[:space:]]+)?KYTY_GUEST_MEMORY_MB=[^#]*)(#.*)?$/\1; [ -n "${BC5_0330_GUEST_MB:-}" ] \&\& export KYTY_GUEST_MEMORY_MB=$BC5_0330_GUEST_MB  # exp 0330/' "$LAUNCH"
sed -i -E '/\\$/!s/^([[:space:]]*(export[[:space:]]+)?BC5_DIRECT_LAZY_NAMES=[^#]*)(#.*)?$/\1; [ -n "${BC5_0330_LAZY:-}" ] \&\& export BC5_DIRECT_LAZY_NAMES=$BC5_0330_LAZY  # exp 0330/' "$LAUNCH"
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0330_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0330_INPUT_CONFIG  # exp 0330\n[ -n "${BC5_0330_LAZY:-}" ] \&\& export BC5_DIRECT_LAZY_NAMES=$BC5_0330_LAZY  # exp 0330\n[ -n "${BC5_0330_GUEST_MB:-}" ] \&\& export KYTY_GUEST_MEMORY_MB=$BC5_0330_GUEST_MB  # exp 0330' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0330.diff"
for h in BC5_0330_INPUT_CONFIG BC5_0330_LAZY BC5_0330_GUEST_MB 'exp0330/wd' 'exp0330/play-last.log'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
chmod +x "$LAUNCH"
eval "LOG=$(sed -n 's/^LOG=\([^ ]*\).*$/\1/p' "$LAUNCH" | head -1)"
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$E"/*) ;; *) echo "the save directory $SDD is not under $E: not started"; exit 1 ;; esac
case "$LOG" in "$E"/*) ;; *) echo "the log $LOG is not under $E: not started"; exit 1 ;; esac
WD=$E/wd; WD99=$(dirname "$L99")/wd; [ -d "$WD99" ] || { echo "no $WD99 to take the layout from: not started"; exit 1; }
mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
for e in "$WD99"/* "$WD99"/.[!.]*; do
  { [ -e "$e" ] || [ -L "$e" ]; } || continue
  n=$(basename "$e"); [ "$n" = _SaveData ] && continue
  if [ -L "$e" ]; then t=$(readlink "$e"); elif [ -e "$W/$n" ]; then t=$W/$n; else echo "exp 0299's wd entry $n is neither a symlink nor in $W: not started"; exit 1; fi
  t=${t//exp0299/exp0330}
  if [ -L "$WD/$n" ] && [ "$(readlink "$WD/$n")" = "$t" ]; then :; else rm -rf "$WD/$n" && ln -s "$t" "$WD/$n" || exit 1; fi
done
SROOT=$WD/_SaveData
case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
echo "launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) ($(grep -c '^[-+][^-+]' "$R/play-pkg-0330.diff") changed lines, $R/play-pkg-0330.diff); wd $WD ($(ls -A "$WD" | wc -l) entries); arms: $ARMS"
SNAP=$E/saves-before-$(date +%H%M)
[ -e "$SNAP" ] && { echo "$SNAP exists: not started"; exit 1; }
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot: not started"; exit 1; }
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES, snapshot $SNAP (comparison only)" | tee -a "$R/s6n-saves.txt"
NA=$(echo $ARMS | wc -w)
echo "exp 0330 | s6n run: the second title's S6N route, RT off, the host's memory, arms $ARMS, ${NA} x $SECS s, exp0330 binary, private wd | start $(date +%H:%M) | until ~$(date -d "+$((NA * (SECS + 75) / 60 + 2)) min" +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0330 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
EP=""; SP=""
abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; [ -n "$SP" ] && kill "$SP" 2> /dev/null; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
LAZY_A=""
one() {  # <arm>: one run; prints pass, CRASH: ..., HANG: ..., DOWN: ... or FAIL: ...
  local ARM=$1 TAG=$1 N T0 ENDED="" J NK NC NT NRT FAIL="" HANG="" CRASH="" DOWN="" ROUTED="" RTOFF="" FL=0 SPAN=0 FPS=0 DUR X
  local -a ENVS=(BC5_EMU="$BIN" KYTY_BC5_RT=0 BC5_0330_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" BC5_DIRECT_BREAKDOWN_AT=540 BC5_DIRECT_BREAKDOWN_NODATA=1 BC5_DIRECT_ZEROSCAN_AT=550)
  local -a WANTENV=("BC5_DIRECT_BREAKDOWN_AT=540" "BC5_DIRECT_ZEROSCAN_AT=550" "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD")
  case "$ARM" in
    B) ENVS+=(BC5_DIRECT_JOURNAL_DONTNEED=1); WANTENV+=("BC5_DIRECT_JOURNAL_DONTNEED=1") ;;
    C) [ -n "$LAZY_A" ] || { echo "FAIL: arm A's lazy list is unknown"; return; }
       X="$LAZY_A,Wwise,SoundAlloc,FileSystem,UIStringAlloc"; [ "$LAZY_A" = "(none)" ] && X="Wwise,SoundAlloc,FileSystem,UIStringAlloc"
       ENVS+=(BC5_0330_LAZY="$X"); WANTENV+=("BC5_DIRECT_LAZY_NAMES=$X") ;;
    D) ENVS+=(BC5_0330_GUEST_MB=12288); WANTENV+=("KYTY_GUEST_MEMORY_MB=12288") ;;
  esac
  EP=""; SP=""
  [ -e "$R/$TAG-start.txt" ] && { echo "FAIL: tag $TAG already used"; return; }
  case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "FAIL: refusing to clear $SROOT"; return ;; esac
  cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "FAIL: the route saves could not be put into $SROOT"; return; }
  find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
  cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
  N=$(sudo -n dmesg 2> /dev/null | wc -l)
  { date '+%F %T'; echo "arm $ARM, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT; env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; } > "$R/$TAG-start.txt"
  "$E/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
  setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
  for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
  T0=$(date +%s)
  if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
  else
    echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
    echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_LAZY_NAMES|BC5_DIRECT_EAGER_NAMES|BC5_DIRECT_JOURNAL|BC5_DIRECT_JOURNAL_DONTNEED|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_BREAKDOWN_NODATA|BC5_DIRECT_ZEROSCAN_AT|BC5_DIRECT_SKIP_PGM|MALLOC_ARENA_MAX|BC5_LEAN)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
    [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
    for w in "${WANTENV[@]}"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
    [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
    if [ "$ARM" = A ]; then LAZY_A=$(envof "$EP" | sed -n 's/^BC5_DIRECT_LAZY_NAMES=//p'); [ -n "$LAZY_A" ] || LAZY_A="(none)"; echo "arm A's lazy list: $LAZY_A" >> "$R/$TAG-start.txt"; fi
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
    nice -n 19 grep -a "^learned 0x\|^hint \|direct memory +\|^learned: fault\|^scratch: window" "$J" > "$R/$TAG-forced.txt"
    nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | tail -1 > "$R/$TAG-pinned.txt"
    read -r FL SPAN <<< "$(nice -n 19 grep -a "VideoOutSubmitFlip took" "$J" | sed -n 's/.*t \([0-9.]*\) s.*/\1/p' | awk 'NR == 1 {a = $1} {b = $1; n++} END {printf "%d %.1f\n", n, b - a}')"
    FPS=$(awk -v n="${FL:-0}" -v s="${SPAN:-0}" 'BEGIN {if (s > 0) printf "%.1f", n / s; else printf "0"}')
  else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
  sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
  find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
  NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt")
  sleep 2
  X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
  echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${X:-no launcher exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt"), RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; $(cat "$R/$TAG-pinned.txt" 2> /dev/null | cut -c1-120); zero scan: $(grep -a '^  total' "$R/$TAG-zeroscan.txt" 2> /dev/null | sed 's/^  total *//')" > "$R/$TAG-summary.txt"
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
for a in $ARMS; do
  echo "== $(date +%T) arm $a"
  one "$a"
  SN=$(saves); echo "$(date '+%F %T') after $a live saves $SN (want $WANT_SAVES)" >> "$R/s6n-saves.txt"
  [ "$SN" = "$WANT_SAVES" ] || { echo "== $(date +%T) THE LIVE SAVES CHANGED after $a: the chain stops"; break; }
  grep -q "^FAIL\|^DOWN" "$R/$a-verdict.txt" 2> /dev/null && { echo "== $(date +%T) the chain stops after $a"; break; }
done
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
[ "$S1" = "$WANT_SAVES" ] || echo "THE LIVE SAVES ARE NOT $WANT_SAVES (snapshot $SNAP): tell the maintainer before anything is restored"
sync
grep -q "^exp 0330 | s6n run" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
