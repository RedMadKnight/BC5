#!/usr/bin/env bash
# BC5 experiment 0401, the night tests of 2026-11-04 (the top session's GO on the maintainer's "przetestuj też buildy z portami
# i przełącznikami z researchu", unattended, no player): one arm of the second title on a private binary, after exp 0382's
# s6n0382.sh (its route gate, its private working directory and save snapshot, its derived launcher), without its shots.
#   MODE=start  the start check: the title reaches the save-slot list (the list runs after the first cross); then it ends.
#   MODE=route  the scripted route to slot 4 (cross, down x3, cross, cross), gated on the journal's frame profile lines; then
#               gameplay until G+<play s> or the cap.
# The binary is given with its md5; the switches are env words (KEY=VALUE ...). RT on and JobArenaFix on, in a private
# copy of input.cfg. The live saves are not read, compared or written (exp 0401 e10, LESSONS R45): the route save is ONE
# named snapshot, $E/saves-named/PPSA03671, made once by MODE=name from an earlier arm's own snapshot; every arm checks its
# sum, resets the private working directory's copy from it, and hashes that copy before and after. The freeze watcher (the top session's exp0401e3/freeze-watch.sh and freeze-dump.sh,
# read-only gdb) and exp 0330's memory sampler run beside the emulator. BOX-LOCK by an atomic hard-link claim; only our
# exact line is removed at the end. The kernel log is streamed by the laptop, not here.
# Series e10 (2026-11-06, exp 0408 sections E and G6): three runner words, read here and passed on unchanged:
#   BC5_0401T_LEARNED=empty   the arm's learned file starts empty instead of a copy of the live one. Each window the title
#                             then needs outside the eager heaps is a GPU fault and a ring reset (F88); the first one ends
#                             the arm under the stop rule below.
#   BC5_0401T_MOUNT=<a bc5-mount under ~/bc5-work/exp0401*> with BC5_0401T_MOUNT_MD5=<its md5>: the derived launcher starts
#                             that mount (exp 0381's setup0381r.sh swap) with its own log, exp0401t/mount-<tag>.log. No
#                             bc5-mount may run at the start (the launcher would reuse its mount); the running mount's md5
#                             and every BC5_MOUNT_* word of the arm are checked in its environment. A BC5_MOUNT_* word
#                             without a private mount is refused (the shared mount may not know it).
#   BC5_0401T_WALK=<s>        route mode only: from G, <s> s of exp 0379's walk (gtt/mk-walk0379.py): the left stick
#                             forward 15 s, a right-stick turn of 1.2 s that changes side every fourth cycle, 0.3 s pause.
#   BC5_0401T_LAUNCHER=exp0409  the arm's launcher comes from ~/bc5-work/exp0409/play-pkg-0409.sh (e4253b93: the
#                             unpacked game through BC5_GAME_DIR, no bc5-mount) instead of play-pkg.sh (exp 0409 arms).
# Every arm also writes <tag>-io.txt: each minute the mount's and the emulator's rchar and read_bytes (/proc/<pid>/io), to
# tell whether the arm streamed, and the learned file's line count at the end.
# usage (on the box): MODE=start|route run0401t.sh <the named snapshot's sum, LC_ALL=C> <tag> <cap s> <play s> <binary> <md5> [KEY=VALUE ...]
#                     MODE=name run0401t.sh <its sum> <tag of an earlier arm whose snapshot $E/saves-<tag> becomes the named one>
# The sum: LC_ALL=C; (cd <dir> && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16) (exp 0253's).
set -u
export LC_ALL=C
MODE=${MODE:-start}
sumof() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's method, LC_ALL=C, over <dir>/PPSA03671
if [ "$MODE" = name ]; then   # exp 0401 e10 (LESSONS R45): the one named snapshot, copied from an earlier arm's own; the live saves are not read
  E=$HOME/bc5-work/exp0401t; NS=$E/saves-named; SUMW=${1:?the snapshot sum}; SRC=${2:?the tag of an earlier arm}
  case "$SRC" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
  [ ! -e "$NS" ] || { echo "$NS exists: not made again"; exit 1; }
  [ -d "$E/saves-$SRC" ] && [ ! -L "$E/saves-$SRC" ] || { echo "no snapshot $E/saves-$SRC"; exit 1; }
  mkdir -p "$NS" && cp -a "$E/saves-$SRC" "$NS/PPSA03671" || { rm -rf "$NS"; echo "the copy failed"; exit 1; }
  got=$(sumof "$NS")
  [ "$got" = "$SUMW" ] || { rm -rf "$NS"; echo "the copy reads $got, not $SUMW: removed"; exit 1; }
  echo "named snapshot $NS/PPSA03671: $got (from $E/saves-$SRC)"
  exit 0
fi
EXPECT_SAVES=${1:?the named snapshot sum}; TAG=${2:?a tag}; SECS=${3:?the cap}; PLAY=${4:?the play seconds}; BIN=${5:?a binary}; WANT=${6:?its md5}
shift 6
SWITCHES=("$@")
case "$MODE" in start | route) ;; *) echo "MODE is start or route"; exit 1 ;; esac
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
# Exp 0401 e9: BC5_0401_LATE_UNSET=<NAME>[,<NAME>...] (upper-case names) unsets words the launcher exports itself; never
# the frame profile, which the route gates on.
LEARNED_EMPTY=0; MOUNT_BIN=""; MOUNT_MD5=""; WALK=""; MOUNT_WORDS=(); L409=0  # exp 0401 e10; L409: exp 0409's launcher
for w in "${SWITCHES[@]}"; do
  case "$w" in
    BC5_0401_LATE_UNSET=*)
      v=${w#BC5_0401_LATE_UNSET=}
      [[ "$v" =~ ^[A-Z][A-Z0-9_]*(,[A-Z][A-Z0-9_]*)*$ ]] || { echo "BC5_0401_LATE_UNSET is a comma list of names: not started"; exit 1; }
      case ",$v," in *,BC5_DIRECT_FRAME_PROFILE,*) echo "the route needs BC5_DIRECT_FRAME_PROFILE: not started"; exit 1 ;; esac ;;
    BC5_0401T_LEARNED=*) [ "${w#*=}" = empty ] || { echo "BC5_0401T_LEARNED takes only empty: not started"; exit 1; }; LEARNED_EMPTY=1 ;;
    BC5_0401T_MOUNT=*)
      MOUNT_BIN=${w#*=}
      case "$MOUNT_BIN" in "$HOME"/bc5-work/exp0401*/bc5-mount) ;; *) echo "BC5_0401T_MOUNT names a bc5-mount under ~/bc5-work/exp0401*: not started"; exit 1 ;; esac
      case "$MOUNT_BIN" in *..* | *[!A-Za-z0-9/_.-]*) echo "BC5_0401T_MOUNT is a plain path: not started"; exit 1 ;; esac ;;
    BC5_0401T_MOUNT_MD5=*) MOUNT_MD5=${w#*=}; [[ "$MOUNT_MD5" =~ ^[0-9a-f]{32}$ ]] || { echo "BC5_0401T_MOUNT_MD5 is an md5: not started"; exit 1; } ;;
    BC5_0401T_LAUNCHER=*) [ "${w#*=}" = exp0409 ] || { echo "BC5_0401T_LAUNCHER takes only exp0409: not started"; exit 1; }; L409=1 ;;
    BC5_0401T_WALK=*) WALK=${w#*=}; [[ "$WALK" =~ ^[0-9]+$ ]] && [ "$WALK" -ge 60 ] && [ "$WALK" -le 3000 ] || { echo "BC5_0401T_WALK is 60-3000 s: not started"; exit 1; } ;;
    BC5_MOUNT_*=*) MOUNT_WORDS+=("$w") ;;
  esac
done
{ [ -n "$MOUNT_BIN" ] && [ -n "$MOUNT_MD5" ]; } || { [ -z "$MOUNT_BIN" ] && [ -z "$MOUNT_MD5" ]; } || { echo "BC5_0401T_MOUNT and BC5_0401T_MOUNT_MD5 come together: not started"; exit 1; }
[ "${#MOUNT_WORDS[@]}" = 0 ] || [ -n "$MOUNT_BIN" ] || { echo "a BC5_MOUNT_* word needs BC5_0401T_MOUNT: not started"; exit 1; }
[ -z "$WALK" ] || [ "$MODE" = route ] || { echo "BC5_0401T_WALK is for route arms: not started"; exit 1; }
[ -z "$WALK" ] || [ "$WALK" -le "$PLAY" ] || { echo "the walk is longer than the play: not started"; exit 1; }
[ "$SECS" -ge 120 ] && [ "$SECS" -le 3000 ] || { echo "the cap is 120-3000 s"; exit 1; }   # e11: up to 3000 s for the ~40-min arm
W=$HOME/bc5-work; E=$W/exp0401t; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330
NS=$E/saves-named   # exp 0401 e10: the one named snapshot (MODE=name)
LAUNCH_SRC=$W/play-pkg.sh; [ "$L409" = 0 ] || LAUNCH_SRC=$W/exp0409/play-pkg-0409.sh; LAUNCH=$E/play-pkg-0401t.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
FW=$W/exp0401e3/freeze-watch.sh; FD=$W/exp0401e3/freeze-dump.sh
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$WANT" ] || { echo "$BIN is not md5 $WANT: not started"; exit 1; }
[ -x "$LAUNCH_SRC" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] && [ -f "$FW" ] && [ -f "$FD" ] || { echo "no $LAUNCH_SRC, sample0330.sh, $LEARN_SRC, $FW or $FD"; exit 1; }
if [ -n "$MOUNT_BIN" ]; then   # exp 0401 e10
  [ -x "$MOUNT_BIN" ] && [ "$(md5sum < "$MOUNT_BIN" | cut -d' ' -f1)" = "$MOUNT_MD5" ] || { echo "$MOUNT_BIN is not md5 $MOUNT_MD5: not started"; exit 1; }
  pgrep -x bc5-mount > /dev/null && { echo "a bc5-mount runs, and the launcher would reuse its mount: not started"; exit 1; }
fi
[ -d "$NS/PPSA03671" ] && [ ! -L "$NS" ] || { echo "no named snapshot $NS (MODE=name makes it): not started"; exit 1; }
NSUM=$(sumof "$NS")
[ "$NSUM" = "$EXPECT_SAVES" ] || { echo "the named snapshot reads $NSUM (LC_ALL=C), not $EXPECT_SAVES: not started"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
# The lock: free is an empty BOX-LOCK. The empty file goes aside, our line is hard-linked in (ln fails if anyone
# recreated it), and a writer who had the old file open shows up in the aside copy (box0401.sh's claim_inner).
T=$(date +%Y%m%d%H%M%S)$$
LINE="water exp 0401t | arm $TAG ($MODE, cap $SECS s), the second title on $(basename "$(dirname "$(dirname "$BIN")")")/$(md5sum < "$BIN" | cut -c1-8), unattended night test, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0401t-$$.new; al=$LOCK.0401t-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || { echo "the lock does not read back as ours: not started"; exit 1; }
printf '%s\n' "water exp 0401t | claimed: arm $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
release() {
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then
    local t=$LOCK.0401t-$$.rel
    grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"
  fi
  printf '%s\n' "water exp 0401t | released: arm $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
EP=""; SP=""; FP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$SP" ] && kill "$SP" 2> /dev/null; [ -n "$FP" ] && kill "$FP" 2> /dev/null
  release
}
trap cleanup EXIT
trap 'echo "$(date "+%F %T") $TAG aborted" >> "$R/saves.txt"; exit 1' HUP INT TERM
# 1. The private input configuration (RT on, JobArenaFix on) and the private learned file.
CFG=$E/input-$TAG.cfg
{ grep -v -i "^RayTracing\.PPSA03671=\|^JobArenaFix\.PPSA03671=" "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; echo "JobArenaFix.PPSA03671=on"; } > "$CFG" || exit 1
if [ "$LEARNED_EMPTY" = 1 ]; then : > "$LEARN" || exit 1; else cp -p "$LEARN_SRC" "$LEARN" || exit 1; fi  # exp 0401 e10: BC5_0401T_LEARNED
# 2. The derived launcher: exp 0382's four changed lines and one added line, checked by anchor and by diff size.
PLAY_PKG_MD5=${PLAY_PKG_MD5:-97835f8850cc22ece5c4bcdbbb646912}; [ "$L409" = 0 ] || PLAY_PKG_MD5=e4253b93b63fd26ffa41fb49c0705c4d   # exp 0409's launcher with ulimit -c 0 (11-09)
LOGA='LOG=~/bc5-work/play-pkg-last.log'; [ "$L409" = 0 ] || LOGA='LOG=/home/kjaniszewski/bc5-work/exp0409/play-last.log  # exp 0409: own log'
[ "$(md5sum < "$LAUNCH_SRC" | cut -d' ' -f1)" = "$PLAY_PKG_MD5" ] || { echo "$LAUNCH_SRC is not $PLAY_PKG_MD5: not started"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk "$LOGA"
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
awk -v a="$LOGA" -v b='LOG=~/bc5-work/exp0401t/play-last.log  # exp 0401t: own log' '$0 == a {print b; next} {print}' "$LAUNCH" > "$LAUNCH.t" && mv -f "$LAUNCH.t" "$LAUNCH" || exit 1   # exact text, no sed pattern
sed -i \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0401t/wd  \# exp 0401t: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0401t/wd/_SaveData-pkg-play  \# exp 0401t: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0401t/direct-learned-pkg.txt  \# exp 0401t: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0401T_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0401T_INPUT_CONFIG  # exp 0401t' "$LAUNCH" || exit 1
sed -i '/^cd ~\/bc5-work\/exp0401t\/wd  /i [ -z "${BC5_0401_LATE_UNSET:-}" ] || unset ${BC5_0401_LATE_UNSET//,/ }  # exp 0401 e9: launcher words an arm takes back' "$LAUNCH" || exit 1
NL=10
if [ -n "$MOUNT_BIN" ]; then   # exp 0401 e10: the private mount and its own log (two more lines changed)
  chk 'BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount'
  chk 'MLOG=~/bc5-work/play-pkg-mount.log'
  sed -i -e "s#^BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount\$#BM=$MOUNT_BIN  \# exp 0401 e10: a private mount#" \
         -e "s#^MLOG=~/bc5-work/play-pkg-mount\.log\$#MLOG=$E/mount-$TAG.log  \# exp 0401 e10: its own mount log#" "$LAUNCH" || exit 1
  NL=14
fi
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0401t.diff"
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0401t.diff")" = "$NL" ] || { echo "the derived launcher's diff is not 4 lines changed + 2 added (+ 2 changed with a private mount): not started"; exit 1; }
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
chmod +x "$LAUNCH"
LOG=$E/play-last.log
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$E"/*) ;; *) echo "the save directory $SDD is not under $E: not started"; exit 1 ;; esac
# 3. The private working directory: exp 0330's layout, its symlinks into ~/bc5-work copied as they are.
WD=$E/wd; WD30=$E30/wd; [ -d "$WD30" ] || { echo "no $WD30: not started"; exit 1; }
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied"; exit 1; }
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] || { echo "$WD/_SaveData or $SDD is not a private directory"; exit 1; }
# 4. The route save: the private copy reset from the named snapshot and hashed (exp 0401 e10, LESSONS R45).
rm -rf "$WD/_SaveData/PPSA03671" && cp -a "$NS/PPSA03671" "$WD/_SaveData/PPSA03671" || { echo "the route saves could not be put in place"; exit 1; }
WSUM=$(sumof "$WD/_SaveData")
[ "$WSUM" = "$NSUM" ] || { echo "the private copy reads $WSUM, not the named snapshot's $NSUM: not started"; exit 1; }
echo "$(date '+%F %T') $TAG the private copy reset from the named snapshot $NSUM" >> "$R/saves.txt"
CMD=$E/in-$TAG.cmd
printf 'wait 1000\n' > "$CMD"; rm -f "$CMD.done"
ENVS=(BC5_EMU="$BIN" BC5_0401T_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$CMD" "${SWITCHES[@]}")
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG, mode $MODE, cap $SECS s, play $PLAY s, binary $BIN md5 $WANT, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8)"; echo "env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; echo "learned file: $([ "$LEARNED_EMPTY" = 1 ] && echo empty || echo "a copy of $LEARN_SRC"), $(grep -c . "$LEARN") lines; mount: ${MOUNT_BIN:-the shared one}; walk: ${WALK:-none}"; } > "$R/$TAG-start.txt"
"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""; MPID=""; IOT=0; WALKED=0  # exp 0401 e10: MPID, IOT, WALKED
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
iof() { if [ -n "$1" ] && [ -r "/proc/$1/io" ]; then awk '/^rchar:/ {r = $2} /^read_bytes:/ {b = $2} END {printf "%s %s", r, b}' "/proc/$1/io"; else printf '? ?'; fi; }  # exp 0401 e10
wk() {   # exp 0401 e10: BC5_0401T_WALK's cycles into the input script, then the sticks centred
  local c=0 t=0 side
  while [ $((t + 16500)) -le $((WALK * 1000)) ]; do
    side=255; [ $(((c / 4) % 2)) = 1 ] && side=0
    printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$side" >> "$CMD"
    c=$((c + 1)); t=$((t + 16500))
  done
  printf 'stick l 128 128\nstick r 128 128\n' >> "$CMD"
  echo "$c"
}
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  [ "$(md5sum < "/proc/$EP/exe" | cut -d' ' -f1)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${SWITCHES[@]}" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "KYTY_BC5_INPUT_CONFIG=$CFG"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  MPID=$(pgrep -n -x bc5-mount)   # exp 0401 e10
  if [ -n "$MOUNT_BIN" ] && [ -z "$ENDED" ]; then
    if [ -z "$MPID" ]; then ENDED="SETUP: no bc5-mount runs"
    else
      echo "mount pid $MPID exe $(readlink "/proc/$MPID/exe")" >> "$R/$TAG-start.txt"
      [ "$(md5sum < "/proc/$MPID/exe" | cut -d' ' -f1)" = "$MOUNT_MD5" ] || ENDED="SETUP: the mount is not md5 $MOUNT_MD5"
      for w in "${MOUNT_WORDS[@]}"; do envof "$MPID" | grep -qxF -- "$w" || { ENDED="SETUP: the mount's environment lacks $w"; break; }; done
    fi
  fi
  echo "# t mount_rchar mount_read_bytes emu_rchar emu_read_bytes (mount pid ${MPID:-none}, emulator pid $EP)" > "$R/$TAG-io.txt"
  bash "$FW" "$LOG" "$FD" "$R/freeze-$TAG" < /dev/null > "$R/$TAG-freeze-watch.txt" 2>&1 & FP=$!
fi
gate() {
  tail -c 3000000 "$1" | grep -a "^frame profile: t" | tail -400 | sed -n 's/^frame profile: t \([0-9.]*\) s, \([0-9.]*\) ms since.*/\1 \2/p' |
    awk 'NF == 2 {n++; t[n] = $1; m[n] = $2} END {if (n < 5) {print 0, 0, 0; exit} c = 0; for (i = n; i >= 1 && t[i] >= t[n] - 3; i--) c++; s = 1; for (i = n - 4; i <= n; i++) if (m[i] <= 55) s = 0; printf "%s %.1f %d\n", t[n], c / 3, s}'
}
J=""; RS=0; K=0; FASTN=0; PREV=0; LOADT=""; G=""; LISTED=""
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  NOW=$(($(date +%s) - T0))
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $NOW s"; break; }
  if [ "$NOW" -ge "$IOT" ]; then echo "$NOW $(iof "$MPID") $(iof "$EP")" >> "$R/$TAG-io.txt"; IOT=$((IOT + 60)); fi   # exp 0401 e10
  if [ -z "$J" ] && [ "$NOW" -ge 60 ]; then
    J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
    if [ ! -f "$J" ] || [ "$(stat -c %Y "$J")" -lt "$T0" ]; then ENDED="SETUP: no journal of this run by $NOW s"; break; fi
  fi
  if [ -n "$J" ] && [ "$RS" -lt 4 ] && [ "$NOW" -ge 85 ]; then
    read -r NT FPS3 SLOW5 <<< "$(gate "$J")"
    FRESH=$(awk -v a="${NT:-0}" -v b="$PREV" 'BEGIN {print (a > b) ? 1 : 0}'); PREV=${NT:-0}
    RUNS=15; [ "$RS" = 3 ] && RUNS=20
    if [ "$FRESH" = 1 ] && awk -v f="${FPS3:-0}" -v r="$RUNS" 'BEGIN {exit !(f >= r)}'; then FASTN=$((FASTN + 1)); else FASTN=0; fi
    LOADING=0; { [ "${SLOW5:-0}" = 1 ] || [ "$FRESH" = 0 ]; } && LOADING=1
    echo "$NOW s: stage $RS, newest flip t ${NT:-?}, fresh $FRESH, flips/s ${FPS3:-?}, slow5 ${SLOW5:-?}, runs $FASTN, loading $LOADING, keys done $(cat "$CMD.done" 2> /dev/null || echo 0)" >> "$R/$TAG-route.txt"
    case "$RS" in
      0) if [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=1; K=$NOW; echo "route: cross (start screen) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge 160 ]; then ENDED="ROUTE: the start screen did not run by 160 s"; fi ;;
      1) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 3 ]; then
           LISTED=$NOW; echo "route: the save-slot list runs at $NOW s" >> "$R/$TAG-start.txt"
           if [ "$MODE" = start ]; then ENDED="START OK: the save-slot list runs at $NOW s"; break; fi
           printf 'press down\nwait 400\npress down\nwait 400\npress down\nwait 800\npress cross\n' >> "$CMD"; RS=2; K=$NOW; echo "route: down x3, cross (slot 4) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 90)) ]; then ENDED="ROUTE: the save list did not run within 90 s of its cross"; fi ;;
      2) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=3; K=$NOW; echo "route: cross (Continue) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 60)) ]; then ENDED="ROUTE: the Continue menu did not run within 60 s"; fi ;;
      3) [ -z "$LOADT" ] && [ "$LOADING" = 1 ] && { LOADT=$NOW; echo "route: the load seen at $NOW s" >> "$R/$TAG-start.txt"; }
         if [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 3)) ] && [ "$FASTN" -ge 3 ]; then G=$NOW; RS=4; echo "route: gameplay G = $G s (the load at $LOADT s)" >> "$R/$TAG-start.txt"
         elif [ -z "$LOADT" ] && [ "$NOW" -ge $((K + 40)) ]; then ENDED="ROUTE: no load within 40 s of Continue"
         elif [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 150)) ]; then ENDED="ROUTE: no gameplay within 150 s of the load"; fi ;;
    esac
    [ -n "$ENDED" ] && break
  fi
  if [ -n "$G" ] && [ -n "$WALK" ] && [ "$WALKED" = 0 ]; then WALKED=1; echo "route: walk of $(wk) cycles ($WALK s) queued at $NOW s" >> "$R/$TAG-start.txt"; fi   # exp 0401 e10
  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break
  if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then
    sleep 25
    if sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="GPU HANG: reset failed or MODE1"
    elif sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -q "reset succeeded"; then ENDED="GPU HANG: ring reset succeeded at $(($(date +%s) - T0 - 25)) s"
    else ENDED="GPU HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, no reset line"; fi
    break
  fi
  if [ "$RS" -lt 4 ] && [ "$NOW" -ge 84 ]; then sleep 1; else sleep 5; fi
done
[ -z "$ENDED" ] && [ "$MODE" = route ] && [ -z "$G" ] && ENDED="ROUTE: no gameplay by the cap of $SECS s"
[ -z "$ENDED" ] && [ "$MODE" = route ] && [ $(($(date +%s) - T0)) -lt $((G + PLAY)) ] && ENDED="CAP: stopped at $SECS s, before G+$PLAY"
[ -z "$ENDED" ] && [ "$MODE" = start ] && ENDED="START: no save-slot list by the cap of $SECS s"
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""; [ -n "$FP" ] && kill "$FP" 2> /dev/null; FP=""
# The launcher unmounts the package on its way out (exp 0301: a stuck launcher keeps the mount); wait for it, up to 60 s.
LGONE=no; for _ in $(seq 1 60); do pgrep -f "exp0401t/play-pkg-0401t.sh" > /dev/null || { LGONE=yes; break; }; sleep 1; done
echo "launcher gone: $LGONE" >> "$R/$TAG-start.txt"
echo "$TAG ${ENDED:-ended at G+$PLAY} (after $DUR s; G ${G:-none}, list ${LISTED:-none})" > "$R/$TAG-end.txt"
echo "# learned file at the end: $(grep -c . "$LEARN") lines ($([ "$LEARNED_EMPTY" = 1 ] && echo "started empty" || echo "started as a copy of the live one"))" >> "$R/$TAG-io.txt"   # exp 0401 e10
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
tail -n 30 "$R/$TAG-play.log" > "$R/$TAG-tail.txt"   # exp 0409 arms: a crash record's last 30 lines
{ echo "# play log: $(grep -a -c "exp 0401 pool" "$R/$TAG-play.log") pool lines, $(grep -a -c "AMM virtual-memory unmap\|auto pool exhausted" "$R/$TAG-play.log") AMM fatal lines"
  grep -a "exp 0401 pool\|AMM virtual-memory unmap\|auto pool exhausted\|KYTY_BC5_AMM_SCATTER\|guest memory\|KYTY_GUEST_MEMORY" "$R/$TAG-play.log" | head -300; } > "$R/$TAG-pool.txt"   # exp 0409 arms
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" | head -80 > "$R/$TAG-crash.txt" 2> /dev/null
grep -a "\[bc5\] exp 040[0-9]\|exp 040[0-9]: " "$R/$TAG-play.log" | sort | uniq -c | sort -rn | head -40 > "$R/$TAG-switch-lines.txt"
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  nice -n 19 grep -a "^exp 040[0-9]: " "$J" | sort | uniq -c >> "$R/$TAG-switch-lines.txt"
  nice -n 19 grep -a "timeout probe\|TIMEOUT\|fl crumbs\|exp 0404" "$J" | head -400 > "$R/$TAG-probe.txt"
  nice -n 19 grep -a "^memory (exp 0401)" "$J" > "$R/$TAG-memline.txt"
  { echo "# journal: $(nice -n 19 grep -a -c "exp 0401 pool" "$J") pool lines"; nice -n 19 grep -a "exp 0401 pool" "$J" | head -300; } >> "$R/$TAG-pool.txt"   # exp 0409 arms
  for k in "acb inherit (exp 0403)" "table catcher (exp 0401)" "acb state restore (exp 0381)"; do echo "$k: $(nice -n 19 grep -a -c "$k" "$J")"; done >> "$R/$TAG-journal.txt"
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-memline.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
# The play log's fps counter lines: flips per second, and the seconds with a gap over 100 ms, over the WHOLE run (exp 0401
# e10, LESSONS R11): the counter's t is the emulator's clock and G is the runner's, so no G window is cut here.
FPSL=$(grep -a "fps counter" "$R/$TAG-play.log" | sed -E 's/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\1 \2 \3 \4/' |
  awk 'NF == 4 {n++; f += $2; s += $3; if ($4 > 100) b++; if ($4 > m) m = $4} END {if (s > 0) printf "whole run: %.1f flips/s over %d s, %d seconds with a gap over 100 ms, longest %.0f ms", f / s, s, b, m; else printf "whole run: no fps lines"}')
MFLOOR=$(awk '!/^#/ && NF > 2 {if (min == "" || $2 < min) min = $2} END {print (min == "" ? "?" : min)}' "$R/$TAG-mem.txt" 2> /dev/null)
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called\|--- Error ---" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NF=$(ls "$R/freeze-$TAG" 2> /dev/null | wc -l)
echo "$TAG ($MODE): ${ENDED:-ended at G+$PLAY} after $DUR s (G ${G:-none}, list ${LISTED:-none}); $FPSL; memory floor ${MFLOOR} MiB available (sampler); crash lines $NC, kernel lines $NK, freeze dumps $NF, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt")" > "$R/$TAG-summary.txt"
sync
cat "$R/$TAG-summary.txt"
S1=$(sumof "$WD/_SaveData"); echo "$(date '+%F %T') $TAG the private copy after the arm: $S1 ($([ "$S1" = "$NSUM" ] && echo unchanged || echo "the title wrote it"); the named snapshot $NSUM)" >> "$R/saves.txt"
sync
