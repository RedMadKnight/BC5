#!/usr/bin/env bash
# BC5 exp 0415: one attended measuring run of the second title's loads on the private build L1 (mk0415.sh), RT on, the
# unpacked title. After exp 0412's run0412n.sh (its lock claim, private working directory, derived launcher, save copy,
# environment check, walk), with these differences:
#   - the launcher is derived from the SHARED ~/bc5-work/play-pkg.sh as it is after exp 0413's swap (read only): its
#     log, working directory, save directory and learned file are made private by anchored edits, checked by count and
#     by diff size; the binary is chosen with the launcher's own BC5_EMU word.
#   - the route is gated on the emulator's own counter file (KYTY_BC5_LOAD_STAT, one line a second with the flip
#     count), not on the journal, so the normal and the lean build take the same route; the first cross is sent when
#     the start screen runs (30 flips/s twice after the slow stretch that follows the movies), not at 85 s.
#   - the save is a private copy of the named read-only snapshot (SNAP below), reset before every run; its sum is the
#     copy's own (LC_ALL=C, the recipe of sumof), recorded once in snapshot.sum. Nothing is compared with or written to
#     the live saves.
#   - collectors beside the emulator: col0415.py (host, /proc and /sys only) and perf0415.sh (in the container,
#     perf_event_open on the title's threads only: no ptrace, never a bc5-* thread).
#   - the watchdog is exp 0412's wd0412.sh, used as it is (R_WD_MIB, default 220: a measuring run). R_PERF=0: no perf.
# BOX-LOCK by an atomic hard-link claim; only our exact line is removed. The kernel log is streamed by the laptop.
# usage (on the box): run0415.sh <tag> normal|lean <play s after G> [KEY=VALUE ...]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; R=$E/raw; LOCK=$W/BOX-LOCK; HERE=$(cd "$(dirname "$0")" && pwd)
SNAP=${R_SNAP:-$HOME/bc5-data/saves/PPSA03671-20261111-2100-memory-heavy}
GAME=$HOME/bc5-data/games/PPSA03671
sumof() { (cd "$1" && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }  # of a PPSA03671 directory, from inside it
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
stop() { echo "run0415 STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator is running: not started"
TAG=${1:?a tag}; VAR=${2:?normal or lean}; PLAY=${3:?the play seconds}; shift 3
EXTRA=("$@")
case "$TAG" in *[!A-Za-z0-9]* | "") stop "the tag is letters and digits" ;; esac
case "$PLAY" in *[!0-9]* | "") stop "the play time is seconds" ;; esac
case "$VAR" in normal) BIN=$E/bin/kyty_emulator; PIN="bin/kyty_emulator" ;; lean) BIN=$E/bin-lean/kyty_emulator; PIN="bin-lean/kyty_emulator" ;; *) stop "the variant is normal or lean" ;; esac
for w in "${EXTRA[@]}"; do case "$w" in [A-Z]*=*) ;; *) stop "an extra word is NAME=VALUE: $w" ;; esac; done
SECS=$((PLAY + 240))
mkdir -p "$R" || stop "mkdir"
[ -e "$R/$TAG-start.txt" ] && stop "tag $TAG already used"
WANT=$(m "$BIN"); grep -qxF "$WANT  $PIN" "$E/built.md5" || stop "the binary is not the one in built.md5"
(cd "$HERE" && sha256sum -c --quiet kit.sha256) || stop "the kit is not what was sent"
LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0415.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$E/direct-learned-pkg.txt
[ -f "$LAUNCH_SRC" ] && [ -f "$LEARN_SRC" ] && [ -d "$W/exp0330/wd" ] && [ -x "$W/exp0412/wd0412.sh" ] && [ -d "$GAME" ] || stop "no shared launcher, learned file, exp0330/wd, exp0412/wd0412.sh or game directory"
[ -d "$SNAP" ] && [ ! -L "$SNAP" ] && [ -n "$(ls -A "$SNAP")" ] || stop "the snapshot $SNAP is not a directory with files (it is the PPSA03671 directory itself)"
NSUM=$(sumof "$SNAP")
if [ -s "$E/snapshot.sum" ]; then [ "$NSUM" = "$(cat "$E/snapshot.sum")" ] || stop "the snapshot reads $NSUM, not $(cat "$E/snapshot.sum")"; else echo "$NSUM" > "$E/snapshot.sum"; fi
command -v python3 > /dev/null || stop "no python3 on the host for the collector"
# ---- the lock
T=$(date +%Y%m%d%H%M%S)$$
LINE="exp 0415 | load run $TAG ($VAR, cap $SECS s), the second title on exp0415/${WANT:0:8}, attended, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || stop "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0415r-$$.new; al=$LOCK.0415r-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; stop "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; stop "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || stop "the lock does not read back as ours"
printf '%s\n' "exp 0415 | claimed: load run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
release() {
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0415r-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
  printf '%s\n' "exp 0415 | released: load run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
EP=""; CP=""; PP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ] && [ "$(m "/proc/$EP/exe")" = "$WANT" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$CP" ] && kill "$CP" 2> /dev/null
  release
}
trap cleanup EXIT
trap 'echo "$(date "+%F %T") $TAG aborted" >> "$R/saves.txt"; exit 1' HUP INT TERM
pgrep '^kyty_emulator' > /dev/null && stop "an emulator started during the claim"
# ---- the private input configuration (RT on, JobArenaFix on) and the private learned file
CFG=$E/input-$TAG.cfg
{ grep -v -i "^RayTracing\.PPSA03671=\|^JobArenaFix\.PPSA03671=" "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; echo "JobArenaFix.PPSA03671=on"; } > "$CFG" || stop "the input configuration"
cp -p "$LEARN_SRC" "$LEARN" || stop "the learned file"
# ---- the derived launcher: five lines changed and one added, each anchor exactly once
cp "$LAUNCH_SRC" "$LAUNCH" || stop "the launcher copy"
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { rm -f "$LAUNCH"; stop "anchor [$1] occurs $c times in $LAUNCH_SRC"; }; }
A_LOG='LOG=~/bc5-work/play-pkg-last.log'
A_LEAN='  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log'
A_CD='cd ~/bc5-work'
A_SD='export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
A_LE='export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
A_ENV='done < "$ENVF"'
for a in "$A_LOG" "$A_LEAN" "$A_CD" "$A_SD" "$A_LE" "$A_ENV"; do chk "$a"; done
python3 -I - "$LAUNCH" "$E" << 'PYEOF' || stop "the launcher's edit"
import sys
p, e = sys.argv[1], sys.argv[2]
s = open(p, encoding='utf-8').read()
edits = [
    ('LOG=~/bc5-work/play-pkg-last.log\n', 'LOG=%s/play-last.log  # exp 0415: own log\n' % e),
    ('  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log\n',
     '  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=%s/play-last.log  # exp 0415: own log (the binary comes from BC5_EMU)\n' % e),
    ('\ncd ~/bc5-work\n', '\ncd %s/wd  # exp 0415: the private working directory (its own _SaveData)\n' % e),
    ('export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play\n', 'export KYTY_BC5_SAVEDATA_DIR=%s/wd/_SaveData-pkg-play  # exp 0415: private\n' % e),
    ('export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt\n', 'export BC5_DIRECT_LEARNED=%s/direct-learned-pkg.txt  # exp 0415: a private copy\n' % e),
    ('done < "$ENVF"\n', 'done < "$ENVF"\n[ -n "${BC5_0415_INPUT_CONFIG:-}" ] && export KYTY_BC5_INPUT_CONFIG=$BC5_0415_INPUT_CONFIG  # exp 0415\n'),
]
for old, new in edits:
    if s.count(old) != 1:
        sys.exit('anchor count %d: %r' % (s.count(old), old))
    s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
PYEOF
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/$TAG-launcher.diff"
[ "$(grep -c '^[-+][^-+]' "$R/$TAG-launcher.diff")" = 11 ] || stop "the derived launcher's diff is not 5 lines changed + 1 added"
bash -n "$LAUNCH" || stop "the derived launcher does not parse"
grep -q '^ulimit -c 0' "$LAUNCH" || stop "the derived launcher does not set ulimit -c 0"
grep -q 'BC5_EMU' "$LAUNCH" && grep -q 'BC5_GAME_DIR' "$LAUNCH" || stop "the launcher knows no BC5_EMU or BC5_GAME_DIR: not the swapped one"
grep -n "bc5-work/_SaveData\|play-pkg-last\|play-pkg-lean-last" "$LAUNCH" | grep -v '^[0-9]*:#' | grep -q . && stop "the derived launcher still names a shared save directory or log"
chmod +x "$LAUNCH"
LOG=$E/play-last.log; WD=$E/wd; SDD=$WD/_SaveData-pkg-play; WD30=$W/exp0330/wd
# ---- the private working directory (exp 0330's layout, its symlinks copied as they are) and the save
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || stop "the working directory"
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || stop "the wd links could not be copied"
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] && [ ! -L "$WD" ] || stop "$WD/_SaveData or $SDD is not a private directory"
case "$(readlink -f "$WD/_SaveData")" in "$(readlink -f "$E")"/*) ;; *) stop "the save directory does not resolve under $E" ;; esac  # run0415b: /home is a link to /var/home on this box
rm -rf "$E/wd/_SaveData/PPSA03671" && cp -a "$SNAP" "$WD/_SaveData/PPSA03671" || stop "the saves could not be put in place"
[ "$(sumof "$WD/_SaveData/PPSA03671")" = "$NSUM" ] || stop "the private copy does not read as the snapshot"
echo "$(date '+%F %T') $TAG the private copy reset from the snapshot $NSUM" >> "$R/saves.txt"
# ---- the environment
CMD=$E/in-$TAG.cmd; STAT=$R/$TAG-loadstat.txt
printf 'wait 1000\n' > "$CMD"; rm -f "$CMD.done" "$STAT"
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
[ -n "$WL" ] || stop "no Wayland socket in /run/user/$(id -u)"
WORDS=("BC5_GAME_DIR=$GAME" "BC5_EMU=$BIN" "KYTY_BC5_LOAD_STAT=$STAT" "KYTY_BC5_INPUT_CMD=$CMD" "BC5_0415_INPUT_CONFIG=$CFG" "WAYLAND_DISPLAY=$WL")
[ "$VAR" = lean ] && WORDS+=("BC5_LEAN=1" "BC5_LOGS=1")
ENVS=("${WORDS[@]}" "${EXTRA[@]}")
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "run $TAG ($VAR), cap $SECS s, play $PLAY s, binary $BIN md5 $WANT, launcher $(m "$LAUNCH" | cut -c1-8) from $(m "$LAUNCH_SRC" | cut -c1-8), snapshot $NSUM"
  echo "extra: ${EXTRA[*]:-none}"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; grep -E '^(MemAvailable|SwapFree|SwapTotal):' /proc/meminfo | tr '\n' ' '; echo
  echo "other load: rsync $(pgrep -c -x rsync), load average $(cut -d' ' -f1-3 /proc/loadavg)"; } > "$R/$TAG-start.txt"
setsid nohup python3 -I "$HERE/col0415.py" "$R/$TAG-col.txt" $((SECS + 30)) > /dev/null 2>&1 < /dev/null & CP=$!
setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\''ulimit -c 0; exec /usr/bin/env "$@"'\'' run0415 "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""; WALKED=0
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
wk() {   # exp 0379's walk for PLAY seconds
  local c=0 t=0 side
  while [ $((t + 16500)) -le $((PLAY * 1000)) ]; do
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
  [ "$(m "/proc/$EP/exe")" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${EXTRA[@]}" "KYTY_BC5_LOAD_STAT=$STAT" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "KYTY_BC5_INPUT_CONFIG=$CFG" "KYTY_BC5_INPUT_CMD=$CMD"; do
    envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }
  done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  envof "$EP" | grep -E '^(KYTY_BC5_|BC5_)' | sort > "$R/$TAG-environ.txt"
  setsid nohup bash "$W/exp0412/wd0412.sh" "$EP" "$R/$TAG-watchdog.txt" "${R_WD_MIB:-220}" 60 > /dev/null 2>&1 < /dev/null &
  [ "${R_PERF:-1}" = 1 ] && { setsid nohup distrobox enter ubuntu -- /usr/bin/bash "$HERE/perf0415.sh" "$R/$TAG-perf" $((SECS + 20)) > /dev/null 2>&1 < /dev/null & PP=$!; }
fi
# The gate: from the counter file's second lines, the time of the newest, the flips/s over the last three, and whether a new line came.
gate() {
  tail -n 8 "$STAT" 2> /dev/null | sed -n 's/^s mono_ns=\([0-9]*\) jt_us=\([0-9]*\) .* flip=\([0-9]*\),.*/\1 \2 \3/p' |
    awk 'NF == 3 {n++; t[n] = $1; j[n] = $2; f[n] = $3} END {if (n < 4) {print 0, 0, 0; exit} printf "%.0f %.1f %.1f\n", t[n] / 1e9, j[n] / 1e6, (f[n] - f[n - 3]) / ((t[n] - t[n - 3]) / 1e9)}'
}
RS=0; K=0; FASTN=0; PREV=0; LOADT=""; G=""; LISTED=""; SLOWSEEN=0; SLOWN=0
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  NOW=$(($(date +%s) - T0))
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $NOW s"; break; }
  if [ "$NOW" -ge 30 ] && [ ! -s "$STAT" ]; then ENDED="SETUP: no counter file of this run by $NOW s"; break; fi
  if [ "$RS" -lt 4 ] && [ "$NOW" -ge 12 ]; then
    read -r MT JT FPS3 <<< "$(gate)"
    FRESH=0; [ "${MT:-0}" -gt "$PREV" ] && FRESH=1; PREV=${MT:-0}
    FAST=30; [ "$RS" -ge 1 ] && FAST=15; [ "$RS" = 3 ] && FAST=20
    if [ "$FRESH" = 1 ] && awk -v f="${FPS3:-0}" -v r="$FAST" 'BEGIN {exit !(f >= r)}'; then FASTN=$((FASTN + 1)); else FASTN=0; fi
    if [ "$FRESH" = 1 ] && awk -v f="${FPS3:-0}" 'BEGIN {exit !(f < 24)}'; then SLOWN=$((SLOWN + 1)); else SLOWN=0; fi
    echo "$NOW s: stage $RS, journal t ${JT:-?}, fresh $FRESH, flips/s ${FPS3:-?}, fast $FASTN, slow $SLOWN, slow seen $SLOWSEEN, keys done $(cat "$CMD.done" 2> /dev/null || echo 0)" >> "$R/$TAG-route.txt"
    case "$RS" in
      0) [ "$NOW" -ge 20 ] && [ "$SLOWN" -ge 2 ] && SLOWSEEN=1
         if [ "$SLOWSEEN" = 1 ] && [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=1; K=$NOW; echo "route: cross (start screen) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge 160 ]; then ENDED="ROUTE: the start screen did not run by 160 s (slow seen $SLOWSEEN)"; fi ;;
      1) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 3 ]; then
           LISTED=$NOW; printf 'press cross\n' >> "$CMD"; RS=2; K=$NOW; echo "route: the save-slot list runs; cross (slot 1) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 90)) ]; then ENDED="ROUTE: the save list did not run within 90 s of its cross"; fi ;;
      2) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=3; K=$NOW; echo "route: cross (Continue) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 60)) ]; then ENDED="ROUTE: the Continue menu did not run within 60 s"; fi ;;
      3) [ -z "$LOADT" ] && { [ "$FASTN" = 0 ] || [ "$FRESH" = 0 ]; } && [ "$NOW" -ge $((K + 1)) ] && { LOADT=$NOW; echo "route: the load seen at $NOW s" >> "$R/$TAG-start.txt"; }
         if [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 3)) ] && [ "$FASTN" -ge 3 ]; then G=$NOW; RS=4; echo "route: gameplay G = $G s (the load at $LOADT s)" >> "$R/$TAG-start.txt"
         elif [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 45)) ]; then G=$NOW; RS=4; echo "route: G = $G s BY TIME (45 s after the load at $LOADT s)" >> "$R/$TAG-start.txt"
         elif [ -z "$LOADT" ] && [ "$NOW" -ge $((K + 40)) ]; then ENDED="ROUTE: no load within 40 s of Continue"; fi ;;
    esac
    [ -n "$ENDED" ] && break
  fi
  if [ -n "$G" ] && [ "$WALKED" = 0 ]; then WALKED=1; echo "route: walk of $(wk) cycles ($PLAY s) queued at $NOW s" >> "$R/$TAG-start.txt"; fi
  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break
  if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then
    sleep 25
    if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="GPU HANG: reset failed or MODE1"
    elif sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -q "reset succeeded"; then ENDED="GPU HANG: ring reset succeeded"
    else ENDED="GPU HANG: a kernel amdgpu line, no reset line"; fi
    break
  fi
  if [ "$RS" -lt 4 ]; then sleep 1; else sleep 5; fi
done
[ -z "$ENDED" ] && [ -z "$G" ] && ENDED="ROUTE: no gameplay by the cap of $SECS s"
[ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt $((G + PLAY)) ] && ENDED="CAP: stopped at $SECS s, before G+$PLAY"
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ] && [ "$(m "/proc/$EP/exe")" = "$WANT" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
EP=""
sleep 3; [ -n "$CP" ] && kill "$CP" 2> /dev/null; CP=""
LGONE=no; for _ in $(seq 1 60); do grep -q '^launcher exit' "$R/$TAG-launch.out" 2> /dev/null && { LGONE=yes; break; }; sleep 1; done
PGONE=no; [ -z "$PP" ] && PGONE="not started"; [ -n "$PP" ] && for _ in $(seq 1 90); do grep -q 'scripts written\|no emulator\|none of the threads' "$R/$TAG-perf.log" 2> /dev/null && { PGONE=yes; break; }; sleep 1; done
WHY=""; grep -q "KILLED" "$R/$TAG-watchdog.txt" 2> /dev/null && WHY="; THE WATCHDOG KILLED IT"
echo "launcher gone: $LGONE; perf ended: $PGONE; $(tail -1 "$R/$TAG-launch.out" 2> /dev/null)" >> "$R/$TAG-start.txt"
echo "$TAG ($VAR) ${ENDED:-ended at G+$PLAY}$WHY (after $DUR s; G ${G:-none}, load ${LOADT:-none}, list ${LISTED:-none})" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" | head -80 > "$R/$TAG-crash.txt" 2> /dev/null
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC\|Killed" > "$R/$TAG-dmesg-after.txt"
S1=$(sumof "$WD/_SaveData/PPSA03671"); echo "$(date '+%F %T') $TAG the private copy after the run: $S1 ($([ "$S1" = "$NSUM" ] && echo unchanged || echo "the title wrote it"))" >> "$R/saves.txt"
echo "$(cat "$R/$TAG-end.txt"); counter lines $(grep -c '^s ' "$STAT" 2> /dev/null), marks $(grep -c '^mark ' "$STAT" 2> /dev/null), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), crash lines $(grep -c . "$R/$TAG-crash.txt"), other load at the end: rsync $(pgrep -c -x rsync)" > "$R/$TAG-summary.txt"
sync
cat "$R/$TAG-summary.txt"
