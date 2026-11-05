#!/usr/bin/env bash
# BC5 experiment 0401, the night tests of 2026-11-04 (the top session's GO on the maintainer's "przetestuj też buildy z portami
# i przełącznikami z researchu", unattended, no player): one arm of the second title on a private binary, after exp 0382's
# s6n0382.sh (its route gate, its private working directory and save snapshot, its derived launcher), without its shots.
#   MODE=start  the start check: the title reaches the save-slot list (the list runs after the first cross); then it ends.
#   MODE=route  the scripted route to slot 4 (cross, down x3, cross, cross), gated on the journal's frame profile lines; then
#               gameplay until G+<play s> or the cap.
# The binary is given with its md5; the switches are env words (KEY=VALUE ...). RT on and JobArenaFix on, in a private
# copy of input.cfg. The live saves are compared only, never written: the route save is a fresh snapshot of them, copied
# into the private working directory. The freeze watcher (the top session's exp0401e3/freeze-watch.sh and freeze-dump.sh,
# read-only gdb) and exp 0330's memory sampler run beside the emulator. BOX-LOCK by an atomic hard-link claim; only our
# exact line is removed at the end. The kernel log is streamed by the laptop, not here.
# usage (on the box): MODE=start|route run0401t.sh <live saves sum, LC_ALL=C> <tag> <cap s> <play s> <binary> <md5> [KEY=VALUE ...]
set -u
export LC_ALL=C
MODE=${MODE:-start}
EXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:?the cap}; PLAY=${4:?the play seconds}; BIN=${5:?a binary}; WANT=${6:?its md5}
shift 6
SWITCHES=("$@")
case "$MODE" in start | route) ;; *) echo "MODE is start or route"; exit 1 ;; esac
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
# Exp 0401 e9: BC5_0401_LATE_UNSET=<NAME>[,<NAME>...] (upper-case names) unsets words the launcher exports itself; never
# the frame profile, which the route gates on.
for w in "${SWITCHES[@]}"; do
  case "$w" in
    BC5_0401_LATE_UNSET=*)
      v=${w#BC5_0401_LATE_UNSET=}
      [[ "$v" =~ ^[A-Z][A-Z0-9_]*(,[A-Z][A-Z0-9_]*)*$ ]] || { echo "BC5_0401_LATE_UNSET is a comma list of names: not started"; exit 1; }
      case ",$v," in *,BC5_DIRECT_FRAME_PROFILE,*) echo "the route needs BC5_DIRECT_FRAME_PROFILE: not started"; exit 1 ;; esac ;;
  esac
done
[ "$SECS" -ge 120 ] && [ "$SECS" -le 1200 ] || { echo "the cap is 120-1200 s"; exit 1; }
W=$HOME/bc5-work; E=$W/exp0401t; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330
SD=$W/_SaveData/PPSA03671
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0401t.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
FW=$W/exp0401e3/freeze-watch.sh; FD=$W/exp0401e3/freeze-dump.sh
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$WANT" ] || { echo "$BIN is not md5 $WANT: not started"; exit 1; }
[ -x "$LAUNCH_SRC" ] && [ -x "$E30/sample0330.sh" ] && [ -f "$LEARN_SRC" ] && [ -f "$FW" ] && [ -f "$FD" ] || { echo "no $LAUNCH_SRC, sample0330.sh, $LEARN_SRC, $FW or $FD"; exit 1; }
saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh, LC_ALL=C
LIVE=$(saves)
[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE (LC_ALL=C), not $EXPECT_SAVES: not started"; exit 1; }
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
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# 2. The derived launcher: exp 0382's four changed lines and one added line, checked by anchor and by diff size.
PLAY_PKG_MD5=${PLAY_PKG_MD5:-97835f8850cc22ece5c4bcdbbb646912}
[ "$(md5sum < "$LAUNCH_SRC" | cut -d' ' -f1)" = "$PLAY_PKG_MD5" ] || { echo "$LAUNCH_SRC is not $PLAY_PKG_MD5: not started"; exit 1; }
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC: not started"; rm -f "$LAUNCH"; exit 1; }; }
chk 'done < "$ENVF"'
chk 'LOG=~/bc5-work/play-pkg-last.log'
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0401t/play-last.log  \# exp 0401t: own log#' \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0401t/wd  \# exp 0401t: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0401t/wd/_SaveData-pkg-play  \# exp 0401t: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0401t/direct-learned-pkg.txt  \# exp 0401t: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0401T_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0401T_INPUT_CONFIG  # exp 0401t' "$LAUNCH" || exit 1
sed -i '/^cd ~\/bc5-work\/exp0401t\/wd  /i [ -z "${BC5_0401_LATE_UNSET:-}" ] || unset ${BC5_0401_LATE_UNSET//,/ }  # exp 0401 e9: launcher words an arm takes back' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0401t.diff"
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0401t.diff")" = 10 ] || { echo "the derived launcher's diff is not 4 lines changed + 2 added: not started"; exit 1; }
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
# 4. The route save: a fresh snapshot of the live saves, checked equal, copied into the wd.
SNAP=$E/saves-$TAG
cp -a "$SD" "$SNAP" && diff -rq "$SD" "$SNAP" > /dev/null || { echo "the live saves could not be snapshot"; exit 1; }
echo "$(date '+%F %T') $TAG live saves $LIVE (LC_ALL=C), snapshot $SNAP" >> "$R/saves.txt"
rm -rf "$WD/_SaveData/PPSA03671" && cp -a "$SNAP" "$WD/_SaveData/PPSA03671" && diff -rq "$SNAP" "$WD/_SaveData/PPSA03671" > /dev/null || { echo "the route saves could not be put in place"; exit 1; }
CMD=$E/in-$TAG.cmd
printf 'wait 1000\n' > "$CMD"; rm -f "$CMD.done"
ENVS=(BC5_EMU="$BIN" BC5_0401T_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$CMD" "${SWITCHES[@]}")
N=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG, mode $MODE, cap $SECS s, play $PLAY s, binary $BIN md5 $WANT, launcher $LAUNCH md5 $(md5sum < "$LAUNCH" | cut -c1-8)"; echo "env: ${ENVS[*]}"; echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; } > "$R/$TAG-start.txt"
"$E30/sample0330.sh" "$R/$TAG-mem.txt" $((SECS + 60)) < /dev/null > /dev/null 2>&1 & SP=$!
setsid nohup bash -c 'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  [ "$(md5sum < "/proc/$EP/exe" | cut -d' ' -f1)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${SWITCHES[@]}" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "KYTY_BC5_INPUT_CONFIG=$CFG"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
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
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" | head -80 > "$R/$TAG-crash.txt" 2> /dev/null
grep -a "\[bc5\] exp 040[0-9]\|exp 040[0-9]: " "$R/$TAG-play.log" | sort | uniq -c | sort -rn | head -40 > "$R/$TAG-switch-lines.txt"
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  nice -n 19 grep -a "^exp 040[0-9]: " "$J" | sort | uniq -c >> "$R/$TAG-switch-lines.txt"
  nice -n 19 grep -a "timeout probe\|TIMEOUT\|fl crumbs\|exp 0404" "$J" | head -400 > "$R/$TAG-probe.txt"
  nice -n 19 grep -a "^memory (exp 0401)" "$J" > "$R/$TAG-memline.txt"
  for k in "acb inherit (exp 0403)" "table catcher (exp 0401)" "acb state restore (exp 0381)"; do echo "$k: $(nice -n 19 grep -a -c "$k" "$J")"; done >> "$R/$TAG-journal.txt"
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-probe.txt"; : > "$R/$TAG-memline.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"
find "$HOME/bc5-data/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %s %p\n' 2> /dev/null > "$R/$TAG-devcoredump.txt"
# The play log's fps counter lines: flips per second, and the seconds with a gap over 100 ms; from G when there is a G.
FPSL=$(grep -a "fps counter" "$R/$TAG-play.log" | sed -E 's/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\1 \2 \3 \4/' |
  awk -v g="${G:-0}" -v t0=0 'NF == 4 {n++; f += $2; s += $3; if ($4 > 100) b++; if ($4 > m) m = $4} END {if (s > 0) printf "%.1f flips/s over %d s, %d seconds with a gap over 100 ms, longest %.0f ms", f / s, s, b, m; else printf "no fps lines"}')
MFLOOR=$(awk '!/^#/ && NF > 2 {if (min == "" || $2 < min) min = $2} END {print (min == "" ? "?" : min)}' "$R/$TAG-mem.txt" 2> /dev/null)
NC=$(grep -c "Access violation\|Segmentation\|Aborted\|terminate called\|--- Error ---" "$R/$TAG-crash.txt"); NK=$(grep -c . "$R/$TAG-dmesg-after.txt"); NF=$(ls "$R/freeze-$TAG" 2> /dev/null | wc -l)
echo "$TAG ($MODE): ${ENDED:-ended at G+$PLAY} after $DUR s (G ${G:-none}, list ${LISTED:-none}); $FPSL; memory floor ${MFLOOR} MiB available (sampler); crash lines $NC, kernel lines $NK, freeze dumps $NF, devcoredumps $(grep -c . "$R/$TAG-devcoredump.txt")" > "$R/$TAG-summary.txt"
sync
cat "$R/$TAG-summary.txt"
S1=$(saves); echo "$(date '+%F %T') $TAG live saves $S1 (want $LIVE)" >> "$R/saves.txt"
[ "$S1" = "$LIVE" ] || echo "THE LIVE SAVES ARE NOT $LIVE: tell the top session before anything is restored"
sync
