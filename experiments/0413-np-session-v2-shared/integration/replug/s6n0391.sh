#!/usr/bin/env bash
# BC5 exp 0391: the software replug check of exp 0372 on the SHARED normal build (78f25172, patch 0001 with exp 0372's
# pad audio route): the S6N route, RT on, the audio, measure and input traces on, while replug0391.sh turns the DualSense's
# PipeWire card profile off and on. Derived from coordination/d19/s6n-d19.sh (sha256 d7cf6e33) by mk0391.py; what differs
# (each marked "0391:" where it stands):
#  - run0391.sh owns the lock: this script only checks that BOX-LOCK is this run's exact line (E0391_LOCKLINE), at the start,
#    before the launch and at every poll; it never writes or clears the lock.
#  - one named route snapshot; reset the private working copy and record its hash before each run.
#  - the traces: KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1 in the emulator's environment, proved there.
#  - no stall-sampler requests, no sampler gate, no menu shots (exp 0378/0380's additions, not needed here).
#  - the audio and rumble lines of the play log go to raw/<tag>-audio-lines.txt for check0391.py.
# Called by run0391.sh only. usage: s6n0391.sh <tag> [secs]   (420 s by default)
# Exit: 0 verdict pass, 1 anything else.
# BC5 D19 smoke, derived from exp 0380 s6n0380r1.sh 494ac253 by mks6n-d19.py, then edited by hand for REVIEW-PORTS-06.
# Changes from that first derivation (each marked "d19:" where it stands):
#  - D19_OWNER: required, passed to the emulator, proved in its environment, so d19box.sh can find all our processes.
#  - not started without dmesg access, a devcoredump directory, or an atime-updating mount (no silent empty evidence).
#  - the RT check at >= 180 s could never run inside a < 180 s loop: rt_check runs at 5/6 of the run, normal only.
#  - the route save read leaves a file, -route.txt; the noatime "warned" path is gone.
#  - the environ line also shows BC5_LOGS.
#  - the raw /proc/PID/environ goes to -environ.bin, private before its first byte, never in Git; -start.txt ties it to the pid.
#  - the verdict also rejects TIMEOUT, kernel, devcoredump, RT-off lines, a missing journal (normal), no route read.
#  - the exit status is 0 only for verdict pass; it was always 0 after a run.
# BC5 experiment  0380 (s6n0378.sh by mk-s6n0380.pl; the rebase fix runs) (exp 0372's s6n0372.sh, made by mk-s6n0378.pl): the healthy-frame register baseline of the
# second title. The S6N route RT on with the SHARED normal build (~/bc5-work/kytyplus-build/src/kyty_emulator, md5
# pinned) through a private copy of play-pkg.sh (own log, wd, save directory, learned-file copy; the shared file is
# only read), exp 0196's named route save copy in the private wd. While the scene runs the
# script asks the installed stall sampler (0377, registers only) for forced samples: `echo once` into its force file,
# 20 samples 5 s apart from t 180 s and 20 more from t 450 s. No wave request is ever written (F520).
# Everything else as s6n0372.sh / s6n0368.sh / s6n0350.sh: exp 0330's memory sampler, fdinfo, flips, the summary.
# Historical derivation: s6n0378.sh; current usage is s6n0391.sh <tag> [secs].
set -u
TAG=${1:?a tag}; SECS=${2:-420}; RT=on; VARIANT=normal; OWNER=${D19_OWNER:?}; LOCKLINE=${E0391_LOCKLINE:?}  # 0391: RT on, the shared normal build, run0391.sh's lock line  # d19: the mark of all our processes
case "$RT" in off | on) ;; *) echo "RT is off or on"; exit 1 ;; esac
W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0413r/run; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330  # 0391: private paths
BIN=${D19_BIN:?}; WANT=${BC5_0380_WANT:?}
SWITCHES="KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1 BC5_GAME_DIR=/home/kjaniszewski/bc5-data/games/PPSA03671 BC5_DIRECT_ACB_STATE_RESTORE=1 KYTY_BC5_PTHREAD_FIXES=1 KYTY_BC5_SAVEDATA_FIXES=1 KYTY_BC5_SAVEDATA_EVENT_CB=1 KYTY_BC5_SAVEDATA_SORT=1 KYTY_BC5_AUDIO_FIXES=set,room KYTY_BC5_AMPR_WAITS=1 KYTY_BC5_VIDEOOUT_STATUS=1 KYTY_BC5_EQUEUE_FIXES=1 KYTY_BC5_MMAP_SHIM_FIXES=1 BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_COND_WRITE=1 BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 KYTY_BC5_TLS_FIXES=1 KYTY_BC5_THREAD_SYNC_FIXES=1 KYTY_BC5_SEMA_FIXES=1 BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 BC5_R3_RELEASE_HOLES=1 BC5_R3_MUNMAP_HOLES=1 BC5_R3_FLEX_HINT=1 BC5_R3_DMQ_END=1 BC5_R3_EXEC_EINVAL=1 BC5_R3_QUERY_SIZE=1 KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1 KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_NET=1 KYTY_BC5_FW_AUDIO=1 KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1 BC5_DIRECT_JOURNAL_QUIET=1 KYTY_BC5_EVENT_PENDING_CAP=64 KYTY_BC5_RANGES_FAST=1 KYTY_BC5_PHYSMAP_SORTED=1"  # 0413: the traces, plus the integration's 55 switches as the second title's launcher words (the table off)
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
SAVES=$W/exp0196/saves-before-152617
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0391.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
mkdir -p "$R"
[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
own_lock_q() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }  # 0391
own_lock_q || { echo "the lock is not this run's: not started"; exit 1; }  # 0391: run0391.sh owns the lock
sudo -n dmesg > /dev/null 2>&1 || { echo "no dmesg access, the kernel gate would be empty: not started"; exit 1; }  # d19
[ -d "$HOME/bc5-data/captures/devcoredump" ] || { echo "no devcoredump directory, that gate would be empty: not started"; exit 1; }  # d19
[ -n "$WANT" ] && [ "$(md5sum < "$BIN" | cut -c1-8)" = "$WANT" ] || { echo "$BIN is not md5 ${WANT:-?} (build0358.sh first): not started"; exit 1; }
[ -d "$SAVES" ] && [ -x "$LAUNCH_SRC" ] && [ -f "$W/exp0203/o2-continue.cmd" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] || { echo "no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0330.sh or $LEARN_SRC"; exit 1; }
copy_hash() { (set -o pipefail; export LC_ALL=C; cd "$1" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum | sha256sum | cut -d " " -f1); }  # R45: files and relative names, C byte order, SHA256
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
chk '  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
chk 'export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0413r/run/play-last.log  \# exp 0350/0364: own log#' \
       -e 's#^\(  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator\) LOG=~/bc5-work/play-pkg-lean-last\.log$#\1 LOG=~/bc5-work/exp0413r/run/play-last.log  \# the same own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0413r/run/wd  \# exp 0350/0364: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0413r/run/wd/_SaveData-pkg-play  \# exp 0350/0364: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0413r/run/direct-learned-pkg.txt  \# exp 0350/0364: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0358_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0358_INPUT_CONFIG  # exp 0339' "$LAUNCH" || exit 1
# 0413: the unpacked game, as play-pkg-0413.diff does (three lines of the shared launcher)
python3 - "$LAUNCH" <<'PYEOF' || exit 1
import sys
p = sys.argv[1]
s = open(p).read()
E = [('[ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }\n',
      '[ -n "${BC5_GAME_DIR:-}" ] || [ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }  # 0413: unpacked game\n'),
     ('if ! mountpoint -q "$M"; then\n',
      'if [ -n "${BC5_GAME_DIR:-}" ]; then M=$BC5_GAME_DIR  # 0413: unpacked game\nelif ! mountpoint -q "$M"; then\n'),
     ('mountpoint -q "$M" || { say "Mounting the package failed', '[ -n "${BC5_GAME_DIR:-}" ] || mountpoint -q "$M" || { say "Mounting the package failed')]
for a, b in E:
    assert s.count(a) == 1, a[:50]
    s = s.replace(a, b)
open(p, 'w').write(s)
PYEOF
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0391.diff"
for h in BC5_0358_INPUT_CONFIG 'exp0413r/run/wd' 'exp0413r/run/play-last.log' 'exp0413r/run/direct-learned-pkg.txt'; do grep -q "$h" "$LAUNCH" || { echo "the derived launcher lacks $h: not started"; exit 1; }; done
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0391.diff")" = 18 ] || { echo "the derived launcher's diff is not 5 lines changed + 1 added: not started"; exit 1; }
[ "$(grep -c 'LOG=~/bc5-work/exp0413r/run/play-last\.log' "$LAUNCH")" = 2 ] && ! grep -Eq 'LOG=~/bc5-work/play-pkg(-lean)?-last\.log' "$LAUNCH" || { echo "a log of the derived launcher is not the private one: not started"; exit 1; }
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
[ "$ATIME_OK" = 1 ] || { echo "noatime on $E: the route save read cannot be shown: not started"; exit 1; }  # d19
echo "launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8) ($R/play-pkg-0391.diff); wd $WD ($(ls -A "$WD" | wc -l) entries)"
# 0391: run0391.sh owns the lock; no lock trap
EP=""; SP=""
abort() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; [ -n "$SP" ] && kill "$SP" 2> /dev/null; echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }
trap abort HUP INT TERM
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
ENDED=""; FAIL=""; HANG=""; CRASH=""; DOWN=""; ROUTED=""; RTOFF=""; FL=0; SPAN=0; FPS=0; FDINFO=""; JOK=0; KERN_OK=0; RTAT=$((SECS * 5 / 6))
# d19-gates-begin (test_d19.sh loads this block on its own)
journal_of() { echo "$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log"; }
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
  private_capture "$2" cat "/proc/$1/environ" || return 1
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
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 "^wayland-[0-9]*$")  # 0413: the display, as the other 0413 scripts pass it
ENVS=(WAYLAND_DISPLAY="${WL:-wayland-0}" BC5_EMU="$BIN" BC5_0358_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" D19_OWNER="$OWNER")
[ "$RT" = off ] && ENVS+=(KYTY_BC5_RT=0)
# shellcheck disable=SC2206
ENVS+=($SWITCHES)
WANTENV=("BC5_DIRECT_RING_DEPS=dcb" "BC5_DIRECT_GPU_CHECK=1" "BC5_DIRECT_GPU_CHECK_PRODUCT=1" "BC5_DIRECT_SHADOW_LABELS=1" "BC5_DIRECT_HOST_INDIRECT=learn:1100000000" "BC5_DIRECT_SOFT_WAIT_MS=8" $SWITCHES "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "D19_OWNER=$OWNER")
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
case "$SROOT" in "$E"/*) rm -rf "$SROOT/PPSA03671" ;; *) echo "refusing to clear $SROOT"; exit 1 ;; esac
cp -a "$SAVES" "$SROOT/PPSA03671" && diff -rq "$SAVES" "$SROOT/PPSA03671" > /dev/null || { echo "the route saves could not be put into $SROOT"; exit 1; }
COPY_HASH=$(copy_hash "$SROOT/PPSA03671") || { echo "the private save copy could not be hashed: not started"; exit 1; }
echo "$(date '+%F %T') tag $TAG sample $SAVES private $SROOT/PPSA03671 sha256 $COPY_HASH (C sorted relative file names and SHA256)" | tee -a "$R/s6n-saves.txt"
find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +
cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG, $SECS s, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8), BC5_EMU $BIN md5 $WANT; env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; } > "$R/$TAG-start.txt"
"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
own_lock_q || { echo "the lock is not this run's: not launched"; [ -z "$SP" ] || kill "$SP" 2> /dev/null; exit 1; }  # 0391: the last look before the launch
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
T0=$(date +%s)
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  echo "environ: $(envof "$EP" | grep -E '^(KYTY_BC5_RT|KYTY_BC5_RT_BUILD_PGM|KYTY_BC5_INPUT_CONFIG|KYTY_BC5_SAVEDATA_DIR|KYTY_GUEST_MEMORY_MB|BC5_DIRECT_LAZY_NAMES|BC5_DIRECT_EAGER_NAMES|BC5_DIRECT_LEARNED|BC5_DIRECT_JOURNAL|BC5_DIRECT_JOURNAL_DONTNEED|BC5_DIRECT_BREAKDOWN_AT|BC5_DIRECT_BREAKDOWN_NODATA|BC5_IMPORT_LOG|BC5_DIRECT_SKIP_PGM|MALLOC_ARENA_MAX|BC5_LEAN|BC5_LOGS)=' | tr '\n' ' ')" >> "$R/$TAG-start.txt"
  if CAP=$(save_environ "$EP" "$R/$TAG-environ.bin"); then echo "$CAP" >> "$R/$TAG-start.txt"; else ENDED="SETUP: the emulator's environment could not be saved"; fi  # d19
  [ "$(md5sum < "/proc/$EP/exe" | cut -c1-8)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${WANTENV[@]}"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
fi
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  own_lock_q || { ENDED="SETUP: the lock is no longer this run's"; break; }  # 0391
  if [ -z "$ROUTED" ] && [ $(($(date +%s) - T0)) -ge 60 ]; then
    if find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | grep -q .; then ROUTED=1; echo "routed at $(($(date +%s) - T0)) s: $(find "$SROOT/PPSA03671" -type f -newerat "@$T0" 2> /dev/null | head -1)" > "$R/$TAG-route.txt"  # d19
    else ENDED="SETUP: the route save was not read by 60 s"; break; fi
  fi
  if [ -z "$FDINFO" ] && [ $(($(date +%s) - T0)) -ge 120 ]; then  # exp 0341: the rings the work ran on (amdgpu fdinfo: drm-engine-gfx / drm-engine-compute, ns of GPU time per engine)
    FDINFO=1; { echo "at $(($(date +%s) - T0)) s:"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } > "$R/$TAG-fdinfo.txt"
  fi
  if [ "$VARIANT" = normal ] && [ -z "$RTOFF" ] && [ $(($(date +%s) - T0)) -ge "$RTAT" ]; then  # d19: was >= 180 s, inside a < 180 s loop
    rt_check "$(journal_of)" "$T0" "$RT"; [ -z "$ENDED" ] || break
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
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then { echo "at $DUR s (end):"; cat /proc/$EP/fdinfo/* 2> /dev/null | grep -a "^drm-engine-\|^drm-client-id" | sort | uniq -c; } >> "$R/$TAG-fdinfo.txt"; fi
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""
echo "$TAG ${ENDED:-stopped at $SECS s} (after $DUR s)" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A8 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address" "$R/$TAG-play.log" | head -60 > "$R/$TAG-crash.txt" 2> /dev/null
{ grep -a "experiment 0341 switches\|experiment 0341 at close\|experiment 0346 at close\|experiment 0349\|experiment 0352\|thread trap|amm fault|amm ledger|no pending map\|amm ledger\|no pending map\|cs refused" "$R/$TAG-play.log"; grep -a "experiment 0341 periodic" "$R/$TAG-play.log" | tail -1; grep -a "args histogram" "$R/$TAG-play.log" | tail -2; echo "bo lines: $(grep -a -c 'bc5-direct: bo ' "$R/$TAG-play.log") (userptr map $(grep -a -c 'bo userptr map' "$R/$TAG-play.log"), unmap $(grep -a -c 'bo userptr unmap' "$R/$TAG-play.log"), shared map $(grep -a -c 'bo shared map' "$R/$TAG-play.log"), scratch $(grep -a -c 'bo scratch slot' "$R/$TAG-play.log"))"; grep -a 'bc5-direct: bo ' "$R/$TAG-play.log" | grep -v 'userptr\|shared' | head -20; } > "$R/$TAG-0341.txt" 2> /dev/null   # exp 0341: the backend's lines
{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters
grep -a -E "AudioOut \(exp 0372\)|pad route:|audio trace:|input trace: rumble|rumble: pad instance|AudioOut:" "$R/$TAG-play.log" > "$R/$TAG-audio-lines.txt" 2> /dev/null   # 0391: for check0391.py
J=$(journal_of)
NRT=0; NCR=0
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  JOK=1  # d19
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
if KT=$(sudo -n dmesg 2> /dev/null); then KERN_OK=1; printf '%s\n' "$KT" | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"; else : > "$R/$TAG-dmesg-after.txt"; fi  # d19
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
cmp -s "$LEARN_SRC" "$LEARN" && echo "the private learned file is unchanged" > "$R/$TAG-learned.txt" || diff "$LEARN_SRC" "$LEARN" > "$R/$TAG-learned.txt"
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NT=$(grep -c "TIMEOUT" "$R/$TAG-probe.txt"); ND=$(grep -c . "$R/$TAG-devcoredump.txt")
sleep 2
X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)
echo "$TAG: ${ENDED:-stopped at $SECS s} after $DUR s; ${X:-no launcher exit line}; crash lines $NC, kernel lines $NK, TIMEOUT lines $NT, compute-ring lines $NCR, fdinfo engines $(grep -a -o 'drm-engine-[a-z]*' "$R/$TAG-fdinfo.txt" 2> /dev/null | sort -u | tr '\n' ' '), devcoredumps $ND, RT-off drop lines $NRT, flips $FL over $SPAN s = $FPS flips/s; $(cut -c1-120 "$R/$TAG-pinned.txt" 2> /dev/null); imports $(grep -c "	" "$R/$TAG-imports.txt" 2> /dev/null) (stubs $(grep -c "	stub$" "$R/$TAG-imports.txt" 2> /dev/null)), call lines $(grep -c " call " "$R/$TAG-imports.txt" 2> /dev/null), procparam $(grep -c "procparam" "$R/$TAG-imports.txt" 2> /dev/null); $(head -1 "$R/$TAG-learned.txt")" > "$R/$TAG-summary.txt"
final_verdict > "$R/$TAG-verdict.txt"
sync
cat "$R/$TAG-summary.txt" "$R/$TAG-0358.txt" "$R/$TAG-verdict.txt"
sync
# d19: the lock stays with d19box.sh
[ "$(cat "$R/$TAG-verdict.txt")" = pass ]  # d19: the exit status carries the result
