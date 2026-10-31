#!/usr/bin/env bash
# BC5 exp 0388: one F464 fight run with the job-arena fix on or off, on the shared normal build, RT on.
# Derived from coordination/d19/s6n-d19.sh d7cf6e33 by mk0388.py. What differs (each marked "0388:" where it stands):
#  - the route: exp 0358's save copy, exp 0360's menu script, and the gameplay inputs appended on the journal gate of
#    run0360.sh (REPRO_PHASE2); KYTY_BC5_JOB_ARENA_FIX in the emulator's environment, proved there.
#  - the emulator is the one that carries this run's D19_OWNER token; a foreign one stops the run and is never touched.
#  - the journal is the run's own: BC5_GC_DUMP_DIR from the emulator's environment, not the newest capture directory.
#  - the lock line is checked at every poll; a lost lock stops the run.
#  - every clear of a private directory proves containment first; no live-save snapshot, no shots, no forced samples.
#  - all /proc, kernel and clock reads are small functions, so the stand-ins replace only those.
# Called by run0388.sh only. usage: s6n0388.sh <tag> <secs> <on|off>
# Exit: 0 verdict pass, 1 anything else.
set -u
export LC_ALL=C  # 0388: the save sums are the C-locale ones
TAG=${1:?a tag}; SECS=${2:?secs}; FIX=${3:?on or off}; RT=on; VARIANT=normal; OWNER=${D19_OWNER:?}  # d19: the mark of all our processes
case "$FIX" in on) FIXV=1 ;; off) FIXV=0 ;; *) echo "the fix is on or off"; exit 1 ;; esac
W=${D19_WORK:-$HOME/bc5-work}; EX=$W/exp0388; E=$EX/run; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330
BIN=${D19_BIN:?}; WANT=${BC5_0380_WANT:?}; LOCKLINE=${E0388_LOCKLINE:?}
# 0388: the first letter of the tag is the arm; the check reads the same table
case "$TAG" in
  C*) ARM="KYTY_BC5_0388_TRACE=1" ;;
  G*) ARM="KYTY_BC5_0388_TRACE=1" ;;
  A*) ARM="KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_TRACE=1" ;;
  B*) ARM="KYTY_BC5_0388_CPU_MASK=1 KYTY_BC5_0388_CURRENT_CPU=1 KYTY_BC5_0388_APPLY_AFFINITY=1 KYTY_BC5_0388_TRACE=1" ;;
  D*) ARM="KYTY_BC5_0388_PUSH_SPIN_US=200 KYTY_BC5_0388_TRACE=1" ;;
  E*) ARM="KYTY_BC5_0388_PUSH_SPIN_US=500 KYTY_BC5_0388_TRACE=1" ;;
  F*) ARM="KYTY_BC5_0388_PUSH_UNTIL_TAKEN_US=500 KYTY_BC5_0388_TRACE=1" ;;
  *) echo "no arm for $TAG"; exit 1 ;;
esac
SWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV $ARM"
JOBS=""; T_JOBS=70; DISK_MAX=80; T_ROUTE=60; T_RT=$((SECS * 5 / 6)); T_FD=120; T_P2=88; T_P2_WAIT=30; T_POLL=5; T_POLL_P2=1; T_KERN=25; T_KILL=4; T_SETTLE=3
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
SAVES=$W/exp0358/saves-live-47aefd45; MENU=$W/exp0360/fight1450-menu.cmd; PHASE2=$W/exp0360/fight1450-play.cmd  # 0388: F464's route
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0388.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
mkdir -p "$R"
[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }
# 0388: the box's reads, in one place
now() { date +%s; }
el() { echo $(($(now) - T0)); }
pause() { sleep "$1"; }
emu_pids() { pgrep '^kyty_emulator'; return 0; }
env_raw() { cat "/proc/$1/environ"; }
exe_of() { readlink "/proc/$1/exe"; }
exe_md5() { md5sum < "/proc/$1/exe" | cut -c1-8; }
cwd_of() { readlink -f "/proc/$1/cwd"; }
alive() { [ -d "/proc/$1" ]; }
fdinfo_of() { cat /proc/"$1"/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; }
kern() { sudo -n dmesg 2> /dev/null; }
disk_pct() { df --output=pcent "$HOME" | tail -1 | tr -dc 0-9; }
mount_opts() { findmnt -no OPTIONS -T "$1" 2> /dev/null; }
route_read() { find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null; }
sampler() { "$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!; }
launch() { setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 & }
devcores() { find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null; }
box_settings() { echo "swappiness $(cat /proc/sys/vm/swappiness); kernel $(uname -r); shared normal $(md5sum < "$BIN" | cut -c1-8); learned $(md5sum < "$LEARN_SRC" | cut -c1-8)"; }
boot_line() { echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; }
# Stand-ins load only from a d19-test- path; they replace the functions above and the T_ times, nothing else.
case "${D19_FAKE:-}" in *d19-test-*) . "$D19_FAKE" ;; esac
envof() { env_raw "$1" 2> /dev/null | tr '\0' '\n'; }
is_ours() { envof "$1" | grep -qxF -- "D19_OWNER=$OWNER"; }
own_lock_q() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }
# A directory may be cleared only if it is really inside this experiment: no link on the way, no escape.
contained() {
  local p=$1 r x; [ -e "$p" ] || [ -L "$p" ] || return 0
  [ ! -L "$p" ] && r=$(readlink -f "$p") && x=$(readlink -f "$EX") && [ -n "$x" ] || return 1
  case "$r" in "$x"/*) return 0 ;; *) return 1 ;; esac
}
[ -z "$(emu_pids)" ] || { echo "an emulator is running: not started"; exit 1; }
own_lock_q || { echo "the lock is not this run's: not started"; exit 1; }  # 0388: run0388.sh owns the lock
kern > /dev/null || { echo "no dmesg access, the kernel gate would be empty: not started"; exit 1; }  # d19
[ -d "$HOME/bc5-data/captures/devcoredump" ] || { echo "no devcoredump directory, that gate would be empty: not started"; exit 1; }  # d19
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?}: not started"; exit 1; }
[ -d "$SAVES" ] && [ ! -L "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -s "$MENU" ] && [ -s "$PHASE2" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, $MENU, $PHASE2, sample0330.sh or $LEARN_SRC"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh, C locale
LIVE=$(saves)
# The box's settings, read only (the maintainer's to change)
box_settings > "$R/$TAG-box-settings.txt"
cat "$R/$TAG-box-settings.txt"
# 1. The private input configuration (RT off or on for this title) and the private learned file.
CFG_SRC=$W/input.cfg; CFG=$E/input-rt$RT.cfg
[ -r "$CFG_SRC" ] || { echo "no $CFG_SRC to copy"; exit 1; }
{ grep -v -i "^RayTracing\.PPSA03671=" "$CFG_SRC"; echo "RayTracing.PPSA03671=$RT"; } > "$CFG" || exit 1
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# 2. The derived launcher: play-pkg.sh with its own log, working directory and save directory, and two hooks after the
#    env-file loop (the input configuration, the learned file).
PLAY_PKG_MD5=55531ab6   # D19's pin; run0388.sh checks the full md5
[ "$(md5sum < "$LAUNCH_SRC" | cut -c1-8)" = "$PLAY_PKG_MD5" ] || { echo "$LAUNCH_SRC is md5 $(md5sum < "$LAUNCH_SRC" | cut -c1-8), not $PLAY_PKG_MD5: not started"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC, expected once: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk '  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
chk 'export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all  # exp 0342 (F412, F415): one ring - every compute buffer on the GFX ring (was 0)'
chk 'export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0388/run/play-last.log  \# exp 0350/0364: own log#' \
       -e 's#^\(  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator\) LOG=~/bc5-work/play-pkg-lean-last\.log$#\1 LOG=~/bc5-work/exp0388/run/play-last.log  \# the same own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0388/run/wd  \# exp 0350/0364: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0388/run/wd/_SaveData-pkg-play  \# exp 0350/0364: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0388/run/direct-learned-pkg.txt  \# exp 0350/0364: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0358_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0358_INPUT_CONFIG  # exp 0339' "$LAUNCH" || exit 1
# 0388: the last settings load is bc5-pkg.env. The check runs after it and before each emulator start, the F2 restart too.
PRE='. ~/bc5-work/exp0388/s/prestart0388.sh || exit 97  # exp 0388'
[ "$(grep -c '^~/bc5-work/pad-volume\.sh >> "$LOG"' "$LAUNCH")" = 1 ] && [ "$(grep -c '^  "$EMU" --game "$M" ' "$LAUNCH")" = 1 ] || { echo "the launcher's start lines are not as pinned: not started"; rm -f "$LAUNCH"; exit 1; }
sed -i -e "/^~\/bc5-work\/pad-volume\.sh >> \"\$LOG\"/i $PRE" -e "/^  \"\$EMU\" --game \"\$M\" /i $PRE" "$LAUNCH" || exit 1
[ "$(grep -cxF -- "$PRE" "$LAUNCH")" = 2 ] && [ "$(grep -n -F "$PRE" "$LAUNCH" | head -1 | cut -d: -f1)" -gt "$(grep -n '^  done < "$PKG_ENV"$' "$LAUNCH" | cut -d: -f1)" ] || { echo "the start check is not after the last settings load: not started"; exit 1; }
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0388.diff"
for h in BC5_0358_INPUT_CONFIG 'exp0388/run/wd' 'exp0388/run/play-last.log' 'exp0388/run/direct-learned-pkg.txt' 'COMPUTE_RING=-1'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0388.diff")" = 13 ] || { echo "the derived launcher's diff is not 5 lines changed + 3 added: not started"; exit 1; }
[ "$(grep -c 'LOG=~/bc5-work/exp0388/run/play-last\.log' "$LAUNCH")" = 2 ] && ! grep -Eq 'LOG=~/bc5-work/play-pkg(-lean)?-last\.log' "$LAUNCH" || { echo "a log of the derived launcher is not the private one: not started"; exit 1; }
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
contained "$WD" || { echo "$WD is not inside $EX: not started"; exit 1; }
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied: not started"; exit 1; }
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] || { echo "$WD/_SaveData or $SDD is not a private directory: not started"; exit 1; }
contained "$WD/_SaveData" && contained "$SDD" || { echo "$WD/_SaveData or $SDD is not inside $EX: not started"; exit 1; }
[ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)" = "$(find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play | wc -l)" ] || { echo "the wd link count differs from $WD30: not started"; exit 1; }
[ -z "$(find "$WD30" -mindepth 1 -maxdepth 1 ! -type l ! -name _SaveData ! -name _SaveData-pkg-play)" ] || { echo "$WD30 has entries that are not links: not started"; exit 1; }
SROOT=$WD/_SaveData
case " $(mount_opts "$E" | tr ',' ' ') " in *" noatime "*) ATIME_OK=0 ;; *) ATIME_OK=1 ;; esac
[ "$ATIME_OK" = 1 ] || { echo "noatime on $E: the route save read cannot be shown: not started"; exit 1; }  # d19
echo "launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) ($R/play-pkg-0388.diff); wd $WD ($(ls -A "$WD" | wc -l) entries)"
WANT_SAVES=$(saves)
echo "$(date '+%F %T') live saves $WANT_SAVES (comparison only)" | tee -a "$R/s6n-saves.txt"
# run0388.sh owns the lock
EP=""; SP=""
stop_emu() { if [ -n "$EP" ] && alive "$EP" && is_ours "$EP"; then kill "$EP"; pause "$T_KILL"; alive "$EP" && is_ours "$EP" && kill -9 "$EP" 2> /dev/null; fi; return 0; }  # 0388: only our own
abort() { stop_emu; [ -n "$SP" ] && kill "$SP" 2> /dev/null; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
ENDED=""; FAIL=""; HANG=""; CRASH=""; DOWN=""; ROUTED=""; RTOFF=""; FL=0; SPAN=0; FPS=0; FDINFO=""; JOK=0; KERN_OK=0; RTAT=$T_RT; JRUN=""
# d19-gates-begin (test_d19.sh loads this block on its own)
# d19: normal only, while the run is alive: the journal of this run, and its RT-off drop lines.
rt_check() {  # journal, start time, on|off; sets RTOFF or ENDED
  if [ ! -f "$1" ] || [ "$(stat -c %Y "$1")" -lt "$2" ]; then ENDED="SETUP: no journal of this run by $RTAT s"
  elif [ "$3" = off ]; then
    if grep -aq "ray tracing off:" "$1"; then RTOFF=1; else ENDED="SETUP: no RT-off drop line by $RTAT s: ray tracing is not off"; fi
  else
    if grep -aq "ray tracing off:" "$1"; then ENDED="SETUP: an RT-off drop line by $RTAT s: ray tracing is not on"; else RTOFF=on; fi
  fi
}
# d19: the raw exec environment, for d19manifest.py. Prints the line that ties it to the pid.
private_capture() {  # file, command...: mode 600 from creation, never over an existing file
  local f=$1; shift
  ( umask 077; set -C; "$@" > "$f" && [ -s "$f" ] && [ "$(stat -c %a "$f")" = 600 ] )
}
save_environ() {  # pid, file
  private_capture "$2" env_raw "$1" || return 1
  echo "environ capture pid $1 bytes $(stat -c %s "$2") sha256 $(sha256sum < "$2" | cut -d' ' -f1)"
}
# d19: every gate the run can decide itself; d19gates.py reads the files again.
final_verdict() {
  case "$ENDED" in
    "") ;;
    SETUP:*) FAIL="$FAIL ${ENDED#SETUP: };" ;;
    DOWN:*) DOWN="${ENDED#DOWN: }" ;;
    HANG:*) HANG="${ENDED#HANG: }" ;;
    "ended by itself"*) CRASH="$ENDED" ;;
  esac
  [ "$NC" = 0 ] || CRASH="${CRASH:-crash lines} ($NC crash lines)"
  [ "$KERN_OK" = 1 ] || FAIL="$FAIL the kernel log could not be read at the end;"
  [ "$NK" = 0 ] || FAIL="$FAIL $NK kernel lines;"
  [ "$ND" = 0 ] || FAIL="$FAIL $ND devcoredumps;"
  [ "$NT" = 0 ] || FAIL="$FAIL $NT TIMEOUT lines;"
  [ "$ROUTED" = 1 ] || FAIL="$FAIL the route save read was not seen;"
  if [ "$RT" = on ] && [ "$NRT" != 0 ]; then FAIL="$FAIL $NRT RT-off drop lines;"; fi
  if [ "$VARIANT" = normal ]; then
    [ "$JOK" = 1 ] || FAIL="$FAIL no journal of this run;"
    [ -n "$RTOFF" ] || FAIL="$FAIL the RT check did not run;"
  fi
  if [ -n "$DOWN" ]; then echo "DOWN: $DOWN"; elif [ -n "$HANG" ]; then echo "HANG: $HANG"; elif [ -n "$CRASH" ]; then echo "CRASH: $CRASH"; elif [ -n "$FAIL" ]; then echo "FAIL:$FAIL"; else echo pass; fi
}
# d19-gates-end
ENVS=(BC5_EMU="$BIN" BC5_0358_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" D19_OWNER="$OWNER")
# shellcheck disable=SC2206
ENVS+=($SWITCHES)
WANTENV=("BC5_DIRECT_COMPUTE_RING=-1" "BC5_DIRECT_RING_DEPS=dcb" "BC5_DIRECT_GPU_CHECK=1" "BC5_DIRECT_GPU_CHECK_PRODUCT=1" "BC5_DIRECT_SHADOW_LABELS=1" "BC5_DIRECT_HOST_INDIRECT=learn:1100000000" "BC5_DIRECT_SOFT_WAIT_MS=8" $SWITCHES "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "D19_OWNER=$OWNER")
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
# 0388: what prestart0388.sh must find after the last settings load.
{ echo "lock=$LOCKLINE"
  for w in "${WANTENV[@]}"; do echo "want=$w"; done
  echo "want=KYTY_BC5_INPUT_CMD=$E/in-$TAG.cmd"; echo "want=BC5_0358_INPUT_CONFIG=$CFG"; echo "want=BC5_EMU=$BIN"; echo "want=EMU=$BIN"; echo "want=LOG=$LOG"
  echo "want=HOME=$HOME"; echo "want=ENVF=$W/bc5-run.env"; echo "want=M=$HOME/bc5-data/mnt/pkg-play"; echo "want=PKG=$HOME/bc5-data/pkg/game.pkg"
  echo "want=PLAY_ARGS=$(sed -n 's/^PLAY_ARGS=//p' "$W/bc5-run.env" | tail -1) --fullscreen"
} > "$E/prestart.want.$$" && mv -f "$E/prestart.want.$$" "$E/prestart.want" || { echo "the start check's file could not be written"; exit 1; }
rm -f "$E/prestart.out"
contained "$SROOT/PPSA03671" || { echo "refusing to clear $SROOT/PPSA03671"; exit 1; }
rm -rf "$SROOT/PPSA03671" || exit 1
cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "the route saves could not be put into $SROOT"; exit 1; }
find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
cp "$MENU" "$E/in-$TAG.cmd" || { echo "the menu script could not be copied"; exit 1; }
P2LOAD=""; P2DONE=""; P2GAME=0  # 0388: the fight route's second part
NEWDIRS=$(ls -d "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null)  # 0388: what existed before this run
N=$(kern | wc -l)
{ date '+%F %T'; echo "arm $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT; env: ${ENVS[*]}"; boot_line; } > "$R/$TAG-start.txt"
sampler
T0=$(now)
own_lock_q || { echo "the lock is not this run's: not launched"; [ -z "$SP" ] || kill "$SP" 2> /dev/null; exit 1; }  # 0388: the last look before the launch
launch
# 0388: the emulator is the one with our token. Any other is foreign: the run stops and does not touch it.
for _ in $(seq 1 120); do
  for p in $(emu_pids); do if is_ours "$p"; then EP=$p; else ENDED="SETUP: a foreign emulator $p"; fi; done
  [ -z "$EP" ] && [ -z "$ENDED" ] || break
  pause 0.5
done
if [ -n "$ENDED" ]; then :
elif [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(exe_of "$EP") cwd $(cwd_of "$EP")" >> "$R/$TAG-start.txt"
  echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_LAZY_NAMES|BC5_DIRECT_EAGER_NAMES|BC5_DIRECT_LEARNED|BC5_DIRECT_JOURNAL|BC5_DIRECT_JOURNAL_DONTNEED|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_BREAKDOWN_NODATA|BC5_IMPORT_LOG|BC5_DIRECT_SKIP_PGM|MALLOC_ARENA_MAX|BC5_LEAN|BC5_LOGS|KYTY_BC5_JOB_ARENA_FIX|KYTY_BC5_0388_[A-Z_]*|BC5_GC_DUMP_DIR)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
  if CAP=$(save_environ "$EP" "$R/$TAG-environ.bin"); then echo "$CAP" >> "$R/$TAG-start.txt"; else ENDED="SETUP: the emulator's environment could not be saved"; fi  # d19
  [ "$(exe_md5 "$EP")" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${WANTENV[@]}"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(cwd_of "$EP")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  # 0388: the run's own journal, from its environment, in a directory that did not exist before this run.
  GC=$(envof "$EP" | sed -n 's/^BC5_GC_DUMP_DIR=//p')
  case "$GC" in "$HOME"/bc5-data/captures/play-*/gc) JRUN=$GC/direct.log ;; *) [ -n "$ENDED" ] || ENDED="SETUP: no journal directory of this run in its environment" ;; esac
  case "
$NEWDIRS
" in *"
$GC
"*) [ -n "$ENDED" ] || ENDED="SETUP: the journal directory $GC is older than this run" ;; esac
fi
while [ -z "$ENDED" ] && [ "$(el)" -lt "$SECS" ]; do
  own_lock_q || { ENDED="SETUP: the lock is no longer this run's"; break; }  # 0388
  alive "$EP" || { ENDED="ended by itself at $(el) s"; break; }
  if [ -z "$ROUTED" ] && [ "$(el)" -ge "$T_ROUTE" ]; then
    if route_read | grep -q .; then ROUTED=1; echo "routed at $(el) s: $(route_read | head -1)" > "$R/$TAG-route.txt"  # d19
    else ENDED="SETUP: the route save was not read by $T_ROUTE s"; break; fi
  fi
  if [ -z "$JOBS" ] && [ "$(el)" -ge "$T_JOBS" ]; then  # 0388: how many workers the title made
    JOBS=1; cat /proc/"$EP"/task/*/comm 2> /dev/null | grep -c "^Job " > "$R/$TAG-jobs.txt"
  fi
  if [ -z "$FDINFO" ] && [ "$(el)" -ge "$T_FD" ]; then  # exp 0341: the rings the work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)
    FDINFO=1; { echo "at $(el) s:"; fdinfo_of "$EP"; } > "$R/$TAG-fdinfo.txt"
  fi
  if [ "$VARIANT" = normal ] && [ -z "$RTOFF" ] && [ "$(el)" -ge "$RTAT" ]; then  # d19: was >= 180 s, inside a < 180 s loop
    rt_check "$JRUN" "$T0" "$RT"; [ -z "$ENDED" ] || break
  fi
  D=$(disk_pct); [ -n "$D" ] && [ "$D" -lt "$DISK_MAX" ] || { ENDED="SETUP: the disk is at ${D:-unknown} %"; break; }  # 0388: at every poll
  KL=$(kern) || { ENDED="SETUP: the kernel log could not be read"; break; }
  if printf '%s\n' "$KL" | tail -n +"$((N + 1))" | grep -qi "amdgpu"; then
    pause "$T_KERN"
    if kern | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="DOWN: kernel amdgpu line, reset failed or MODE1"
    elif kern | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then ENDED="HANG: kernel amdgpu line at $(($(el) - T_KERN)) s, ring reset succeeded"
    else ENDED="HANG: kernel amdgpu line at $(($(el) - T_KERN)) s, no reset line"; fi
    break
  fi
  # 0388, from run0360.sh: the gameplay inputs are appended to the input script (the input thread tails it every 20 ms)
  # once the journal shows the load after the menu (the last 5 flips slower than 55 ms) and then gameplay (of the last
  # 25 flips at least 20 faster than 40 ms, the last 3 among them), from 88 s on; 30 s after the load without that they
  # go anyway, and the run then does not count as routed. Every poll is kept in raw/<tag>-phase2.txt.
  if [ -z "$P2DONE" ] && [ "$(el)" -ge "$T_P2" ] && [ -f "$JRUN" ]; then
    P2IV=$(tail -c 400000 "$JRUN" | grep -a "^frame profile: t" | tail -25 | sed -n 's/^frame profile: t [0-9.]* s, \([0-9.]*\) ms since.*/\1/p' | tr '\n' ' ')
    read -r P2SLOW P2FAST <<< "$(echo "$P2IV" | awk '{slow = NF >= 5; for (i = NF - 4; i <= NF && i >= 1; i++) if ($i <= 55) slow = 0; f = 0; for (i = 1; i <= NF; i++) if ($i < 40) f++; fast = NF >= 25 && f >= 20; for (i = NF - 2; i <= NF && i >= 1; i++) if ($i >= 40) fast = 0; print slow + 0, fast + 0}')"
    echo "$(el) s: slow ${P2SLOW:-?} fast ${P2FAST:-?} load ${P2LOAD:-} | $P2IV" >> "$R/$TAG-phase2.txt"
    [ "${P2SLOW:-0}" = 1 ] && [ -z "$P2LOAD" ] && P2LOAD=$(el)
    if { [ -n "$P2LOAD" ] && [ "${P2FAST:-0}" = 1 ]; } || { [ -n "$P2LOAD" ] && [ $(($(el) - P2LOAD)) -ge "$T_P2_WAIT" ]; }; then
      [ "${P2FAST:-0}" = 1 ] && P2GAME=1
      cat "$PHASE2" >> "$E/in-$TAG.cmd" || { ENDED="SETUP: the gameplay inputs could not be appended"; break; }
      P2DONE=$(el)
      echo "phase2 appended $P2DONE load $P2LOAD gameplay $P2GAME lines $(grep -c . "$PHASE2")" | tee "$R/$TAG-phase2-done.txt"
    fi
  fi
  if [ -z "$P2DONE" ] && [ "$(el)" -ge $((T_P2 - 3)) ]; then pause "$T_POLL_P2"; else pause "$T_POLL"; fi
done
DUR=$(el)
if [ -n "$EP" ] && alive "$EP" && is_ours "$EP"; then { echo "at $DUR s (end):"; fdinfo_of "$EP"; } >> "$R/$TAG-fdinfo.txt"; fi
stop_emu
pause "$T_SETTLE"; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""
echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log" || echo "no log of this run: the copy failed" > "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
{ grep -a "experiment 0341 switches\|experiment 0341 at close\|experiment 0346 at close\|experiment 0349\|experiment 0352\|thread trap|amm fault|amm ledger|no pending map\|amm ledger\|no pending map\|cs refused" "$R/$TAG-play.log"; grep -a "experiment 0341 periodic" "$R/$TAG-play.log" | tail -1; grep -a "args histogram" "$R/$TAG-play.log" | tail -2; echo "bo lines: $(grep -a -c 'bc5-direct: bo ' "$R/$TAG-play.log") (userptr map $(grep -a -c 'bo userptr map' "$R/$TAG-play.log"), unmap $(grep -a -c 'bo userptr unmap' "$R/$TAG-play.log"), shared map $(grep -a -c 'bo shared map' "$R/$TAG-play.log"), scratch $(grep -a -c 'bo scratch slot' "$R/$TAG-play.log"))"; grep -a 'bc5-direct: bo ' "$R/$TAG-play.log" | grep -v 'userptr\|shared' | head -20; } > "$R/$TAG-0341.txt" 2> /dev/null   # exp 0341: the backend's lines
{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters
J=$JRUN  # 0388: this run's own
NRT=0; NCR=0
if [ -n "$J" ] && [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  JOK=1  # d19
  if [ -z "$RTOFF" ] && ! grep -aq "ray tracing off:" "$J"; then RTOFF=on; fi  # 0388: a crash ends the run before the live check
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
else echo "no journal of this run (${J:-none})" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; fi
if KT=$(kern); then KERN_OK=1; printf '%s\n' "$KT" | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"; else : > "$R/$TAG-dmesg-after.txt"; fi  # d19
devcores > "$R/$TAG-devcoredump.txt"; DEV_OK=$?
echo "kernel $KERN_OK devcore $([ "$DEV_OK" = 0 ] && echo 1 || echo 0)" > "$R/$TAG-reads.txt"  # 0388: an empty file is not a read
cmp -s "$LEARN_SRC" "$LEARN" && echo "the private learned file is unchanged" > "$R/$TAG-learned.txt" || diff "$LEARN_SRC" "$LEARN" > "$R/$TAG-learned.txt"
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt"); ND=$(grep -c . "$R/$TAG-devcoredump.txt")
X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${X:-no launcher exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, compute-ring lines $NCR, fdinfo engines $(grep -a -o 'drm-engine-[a-z]*' "$R/$TAG-fdinfo.txt" 2> /dev/null | sort -u | tr '\n' ' '), devcoredumps $ND, RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; $(cut -c1-120 "$R/$TAG-pinned.txt" 2> /dev/null); imports $(grep -c "	" "$R/$TAG-imports.txt" 2> /dev/null) (stubs $(grep -c "	stub$" "$R/$TAG-imports.txt" 2> /dev/null)), call lines $(grep -c " call " "$R/$TAG-imports.txt" 2> /dev/null), procparam $(grep -c "procparam" "$R/$TAG-imports.txt" 2> /dev/null); $(head -1 "$R/$TAG-learned.txt")" > "$R/$TAG-summary.txt"
final_verdict > "$R/$TAG-verdict.txt"
sync
cat "$R/$TAG-summary.txt" "$R/$TAG-0358.txt" "$R/$TAG-verdict.txt"
S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"
sync
[ "$(cat "$R/$TAG-verdict.txt")" = pass ]  # d19: the exit status carries the result
