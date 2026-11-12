#!/usr/bin/env bash
# BC5 exp 0412: one unattended arm of the second title on the guardian's build, for the night of 2026-11-10/11 (the
# maintainer: "Przez 3h dzialasz sam i robisz testy i nowe buildy az znajdziesz poprawe", relayed by the top session,
# which gave the box until about 02:00). After exp 0401's run0401t.sh (its route gate on the journal's frame profile
# lines, its private working directory, its derived launcher, its walk), with these differences:
#   - the save is the maintainer's current one: ONE named snapshot, $N/saves-named/PPSA03671, a copy of the live
#     ~/bc5-work/_SaveData/PPSA03671 made once by MODE=name (the live saves are read once there and never written;
#     the sum is the copy's own, under LC_ALL=C: no comparison with the live saves, no new snapshot per arm: lesson R45);
#     every arm resets its private copy from it. The save list has one slot, so the route is cross (start screen),
#     cross (slot 1), cross (Continue).
#   - the arm's words come from play-guard-0412.sh <arm> words (the "e11 unpacked" shortcut's 70 plus the arm's);
#     more KEY=VALUE words may follow on the command line.
#   - beside the emulator: sampler0412b.sh, the fuse (fuse0412.sh, default memory.max 12,400 MiB and swap 1,024 MiB:
#     tighter than the shortcuts' because nobody is at the box) and the watchdog wd0412.sh (SIGKILL under 300 MiB
#     available or over 60 % PSI full for 10 s). A run the watchdog or the fuse ends has hit the wall; that is a result.
#   - from gameplay (G) on: exp 0379's walk for the whole play time.
# RT on and JobArenaFix on in a private copy of input.cfg; a private copy of the learned file per arm.
# BOX-LOCK by an atomic hard-link claim per arm; only our exact line is removed. The kernel log is streamed by the laptop.
# exp 0413 (2026-11-12): derived by mkrun0413.py for the private build of the integration (int/0413-tested-into-shared):
# the binary is P_BIN (pinned P_WANT) through the launcher's BC5_EMU word, the words come from the file P_WORDS, and
# everything written lands in ~/bc5-work/exp0413/n; exp 0412's named snapshot, tools and launcher are only read.
# usage (on the box): run0412n.sh <tag> <arm> <play s after G> [KEY=VALUE ...]      (N_FUSE="<RAM MiB> <swap MiB>", N_CAP=<s>)
#                     MODE=name run0412n.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$X/night/saves-named; NSF=$X/night/saves-named.sum
sumof() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
mkdir -p "$R" || exit 1
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ "${MODE:-}" = name ]; then echo "exp 0413: no MODE=name here (exp 0412 owns the snapshot)"; exit 1
fi
if false; then
  [ ! -e "$NS" ] || { echo "$NS exists ($(cat "$N/saves-named.sum" 2> /dev/null)): not made again"; exit 0; }
  [ -d "$W/_SaveData/PPSA03671" ] || { echo "no live saves"; exit 1; }
  mkdir -p "$NS" && cp -a "$W/_SaveData/PPSA03671" "$NS/PPSA03671" || { rm -rf "$NS"; echo "the copy failed"; exit 1; }
  sumof "$NS" > "$N/saves-named.sum"
  echo "named snapshot $NS/PPSA03671: $(cat "$N/saves-named.sum") ($(du -sh "$NS" | cut -f1), $(find "$NS" -type f | wc -l) files)"
  exit 0
fi
TAG=${1:?a tag}; ARM=${2:?an arm}; PLAY=${3:?the play seconds}; shift 3
EXTRA=("$@")
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
case "$PLAY" in *[!0-9]* | "") echo "the play time is seconds"; exit 1 ;; esac
SECS=${N_CAP:-$((PLAY + 260))}; FUSE=${N_FUSE:-12400 1024}
[ "$SECS" -ge 120 ] && [ "$SECS" -le 3000 ] || { echo "the cap is 120-3000 s"; exit 1; }
BIN=${P_BIN:?the private binary}; LAUNCH_SRC=$X/play-pkg-0412.sh; LAUNCH=$N/play-pkg-0413n.sh; LEARN_SRC=$W/direct-learned-pkg.txt; LEARN=$N/direct-learned-pkg.txt
[ "$(m "$BIN")" = "${P_WANT:?the binary md5}" ] && grep -qxF "$(m "$LAUNCH_SRC")  play-pkg-0412.sh" "$X/built.md5" || { echo "the binary is not P_WANT or the launcher is not the one in built.md5: not started"; exit 1; }
WANT=$(m "$BIN")
for f in sampler0412b.sh fuse0412.sh; do grep -qxF "$(m "$X/$f")  $f" "$X/tools.md5" || { echo "$f is not the installed one: not started"; exit 1; }; done
[ -x "$X/wd0412.sh" ] && [ -f "$LEARN_SRC" ] && [ -d "$W/exp0330/wd" ] || { echo "no wd0412.sh, learned file or exp0330/wd: not started"; exit 1; }
[ -d "$NS/PPSA03671" ] && [ ! -L "$NS" ] && [ -s "$NSF" ] || { echo "no named snapshot of exp 0412: not started"; exit 1; }
NSUM=$(sumof "$NS"); [ "$NSUM" = "$(cat "$NSF")" ] || { echo "the named snapshot reads $NSUM, not $(cat "$NSF"): not started"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
mapfile -t WORDS < <(grep -v "^#" "${P_WORDS:?the words file}" | grep .) && [ "${#WORDS[@]}" -ge 3 ] || { echo "no words in $P_WORDS: not started"; exit 1; }
WORDS+=("BC5_EMU=$BIN")
T=$(date +%Y%m%d%H%M%S)$$
LINE="exp 0413 | private run $TAG ($ARM, cap $SECS s), the second title on exp0413/${WANT:0:8}, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0412n-$$.new; al=$LOCK.0412n-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || { echo "the lock does not read back as ours: not started"; exit 1; }
printf '%s\n' "exp 0413 | claimed: private run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
release() {
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0412n-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
  printf '%s\n' "exp 0413 | released: private run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
EP=""; SP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$SP" ] && kill "$SP" 2> /dev/null
  release
}
trap cleanup EXIT
trap 'echo "$(date "+%F %T") $TAG aborted" >> "$R/saves.txt"; exit 1' HUP INT TERM
# 1. The private input configuration (RT on, JobArenaFix on) and the private learned file.
CFG=$N/input-$TAG.cfg
{ grep -v -i "^RayTracing\.PPSA03671=\|^JobArenaFix\.PPSA03671=" "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; echo "JobArenaFix.PPSA03671=on"; } > "$CFG" || exit 1
cp -p "$LEARN_SRC" "$LEARN" || exit 1
# 2. The derived launcher: four lines changed and one added, checked by anchor and by diff size.
cp "$LAUNCH_SRC" "$LAUNCH" || exit 1
chk() { local c; c=$(grep -cxF -- "$1" "$LAUNCH"); [ "$c" = 1 ] || { echo "anchor [$1] occurs $c times in $LAUNCH_SRC: not started"; rm -f "$LAUNCH"; exit 1; }; }
LOGA="LOG=$X/play-last.log  # exp 0412: own log"
chk 'done < "$ENVF"'
chk "$LOGA"
chk 'cd ~/bc5-work'
chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'
awk -v a="$LOGA" -v b="LOG=$N/play-last.log  # exp 0413: own log" '$0 == a {print b; next} {print}' "$LAUNCH" > "$LAUNCH.t" && mv -f "$LAUNCH.t" "$LAUNCH" || exit 1
sed -i \
       -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0413/n/wd  \# exp 0413: the private working directory (its own _SaveData)#' \
       -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0413/n/wd/_SaveData-pkg-play  \# exp 0413: private#' \
       -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0413/n/direct-learned-pkg.txt  \# exp 0413: a private copy#' "$LAUNCH" || exit 1
sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0412N_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0412N_INPUT_CONFIG  # exp 0412 night' "$LAUNCH" || exit 1
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0413n.diff"
[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0413n.diff")" = 9 ] || { echo "the derived launcher's diff is not 4 lines changed + 1 added: not started"; exit 1; }
bash -n "$LAUNCH" || { echo "the derived launcher does not parse: not started"; exit 1; }
grep -q '^ulimit -c 0' "$LAUNCH" || { echo "the derived launcher does not set ulimit -c 0: not started"; exit 1; }
chmod +x "$LAUNCH"
LOG=$N/play-last.log
eval "SDD=$(sed -n 's/^.*KYTY_BC5_SAVEDATA_DIR=\([^ ;]*\).*$/\1/p' "$LAUNCH" | head -1)"
case "$SDD" in "$N"/*) ;; *) echo "the save directory $SDD is not under $N: not started"; exit 1 ;; esac
# 3. The private working directory: exp 0330's layout, its symlinks into ~/bc5-work copied as they are.
WD=$N/wd; WD30=$W/exp0330/wd
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" "$SDD" || exit 1
  find "$WD30" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied"; exit 1; }
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$SDD" ] && [ ! -L "$SDD" ] || { echo "$WD/_SaveData or $SDD is not a private directory"; exit 1; }
# 4. The save: the private copy reset from the named snapshot.
rm -rf "$WD/_SaveData/PPSA03671" && cp -a "$NS/PPSA03671" "$WD/_SaveData/PPSA03671" || { echo "the saves could not be put in place"; exit 1; }
[ "$(sumof "$WD/_SaveData")" = "$NSUM" ] || { echo "the private copy does not read as the named snapshot: not started"; exit 1; }
echo "$(date '+%F %T') $TAG the private copy reset from the named snapshot $NSUM" >> "$R/saves.txt"
CMD=$N/in-$TAG.cmd
printf 'wait 1000\n' > "$CMD"; rm -f "$CMD.done"
# The desktop's Wayland socket: wayland-0 after most boots, wayland-1 after the reset of 21:56 (the launcher's default is
# wayland-0, and a run over ssh has no WAYLAND_DISPLAY of its own: the pilot p1ledger ended with "wayland not available").
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
[ -n "$WL" ] || { echo "no Wayland socket in /run/user/$(id -u): not started"; exit 1; }
ENVS=("${WORDS[@]}" "${EXTRA[@]}" BC5_0412N_INPUT_CONFIG="$CFG" KYTY_BC5_INPUT_CMD="$CMD" WAYLAND_DISPLAY="$WL")
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "arm $TAG ($ARM), cap $SECS s, play $PLAY s, binary $BIN md5 $WANT, launcher $(m "$LAUNCH" | cut -c1-8), fuse $FUSE"
  echo "the arm's words: $(printf '%s\n' "${ENVS[@]}" | grep -E '^(BC5_GUARD_|BC5_DIRECT_LAZY_RELEASE|BC5_DIRECT_ZERO|BC5_0412)' | tr '\n' ' ')"; echo "extra: ${EXTRA[*]:-none}"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"; grep -E '^(MemAvailable|SwapFree|SwapTotal):' /proc/meminfo | tr '\n' ' '; echo; } > "$R/$TAG-start.txt"
bash "$X/fuse0412.sh" restore "$R/$TAG-fuse.txt"
nohup bash "$X/sampler0412b.sh" "$R/$TAG-sampler.txt" 120 $((SECS + 60)) > /dev/null 2>&1 < /dev/null & SP=$!
# shellcheck disable=SC2086
[ "$FUSE" = 0 ] || setsid nohup bash "$X/fuse0412.sh" set $FUSE "$R/$TAG-fuse.txt" > /dev/null 2>&1 < /dev/null &
setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\''ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"'\'' guard0412n "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""; WALKED=0
envof() { tr '\0' '\n' < "/proc/$1/environ" 2> /dev/null; }
wk() {   # exp 0379's walk for PLAY seconds: the left stick forward 15 s, a right-stick turn of 1.2 s that changes side every fourth cycle
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
  [ "$(md5sum < "/proc/$EP/exe" | cut -d' ' -f1)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  for w in "${WORDS[@]}" "${EXTRA[@]}" "KYTY_BC5_SAVEDATA_DIR=$SDD" "BC5_DIRECT_LEARNED=$LEARN" "KYTY_BC5_INPUT_CONFIG=$CFG"; do envof "$EP" | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  setsid nohup bash "$X/wd0412.sh" "$EP" "$R/$TAG-watchdog.txt" "${N_WD_MIB:-300}" 60 > /dev/null 2>&1 < /dev/null &
  CGC=/sys/fs/cgroup$(cut -d: -f3 "/proc/$EP/cgroup" 2> /dev/null | head -1); OK0=$(awk '$1 == "oom_kill" { print $2 }' "$CGC/memory.events" 2> /dev/null); OK0=${OK0:-0}
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
           LISTED=$NOW; printf 'press cross\n' >> "$CMD"; RS=2; K=$NOW; echo "route: the save-slot list runs; cross (slot 1) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 90)) ]; then ENDED="ROUTE: the save list did not run within 90 s of its cross"; fi ;;
      2) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=3; K=$NOW; echo "route: cross (Continue) at $NOW s" >> "$R/$TAG-start.txt"
         elif [ "$NOW" -ge $((K + 60)) ]; then ENDED="ROUTE: the Continue menu did not run within 60 s"; fi ;;
      3) [ -z "$LOADT" ] && [ "$LOADING" = 1 ] && { LOADT=$NOW; echo "route: the load seen at $NOW s" >> "$R/$TAG-start.txt"; }
         if [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 3)) ] && [ "$FASTN" -ge 3 ]; then G=$NOW; RS=4; echo "route: gameplay G = $G s (the load at $LOADT s)" >> "$R/$TAG-start.txt"
         elif [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 45)) ]; then G=$NOW; RS=4; echo "route: G = $G s BY TIME (45 s after the load at $LOADT s; the title does not reach 20 flips/s: the pilot q1ledger ran at 1-10)" >> "$R/$TAG-start.txt"
         elif [ -z "$LOADT" ] && [ "$NOW" -ge $((K + 40)) ]; then ENDED="ROUTE: no load within 40 s of Continue"
         elif [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 150)) ]; then ENDED="ROUTE: no gameplay within 150 s of the load"; fi ;;
    esac
    [ -n "$ENDED" ] && break
  fi
  if [ -n "$G" ] && [ "$WALKED" = 0 ]; then WALKED=1; echo "route: walk of $(wk) cycles ($PLAY s) queued at $NOW s" >> "$R/$TAG-start.txt"; fi
  [ -n "$G" ] && [ "$NOW" -ge $((G + PLAY)) ] && break
  if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then
    sleep 25
    if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qiE "reset failed|MODE1|mode1"; then ENDED="GPU HANG: reset failed or MODE1"
    elif sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -q "reset succeeded"; then ENDED="GPU HANG: ring reset succeeded at $(($(date +%s) - T0 - 25)) s"
    else ENDED="GPU HANG: kernel amdgpu line at $(($(date +%s) - T0 - 25)) s, no reset line"; fi
    break
  fi
  if [ "$RS" -lt 4 ] && [ "$NOW" -ge 84 ]; then sleep 1; else sleep 5; fi
done
[ -z "$ENDED" ] && [ -z "$G" ] && ENDED="ROUTE: no gameplay by the cap of $SECS s"
[ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt $((G + PLAY)) ] && ENDED="CAP: stopped at $SECS s, before G+$PLAY"
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3; [ -n "$SP" ] && kill "$SP" 2> /dev/null; SP=""
LGONE=no; for _ in $(seq 1 60); do pgrep -f "exp0413/n/play-pkg-0413n.sh" > /dev/null || { LGONE=yes; break; }; sleep 1; done
sleep 3
WHY=""; grep -q "KILLED" "$R/$TAG-watchdog.txt" 2> /dev/null && WHY="; THE WATCHDOG KILLED IT"
OK1=$(awk '$1 == "oom_kill" { print $2 }' "${CGC:-/nonexistent}/memory.events" 2> /dev/null); OK1=${OK1:-0}
[ "$OK1" -gt "${OK0:-0}" ] && WHY="$WHY; THE FUSE KILLED IT (oom_kill ${OK0:-0} -> $OK1)"
echo "launcher gone: $LGONE; $(tail -1 "$R/$TAG-launch.out" 2> /dev/null)" >> "$R/$TAG-start.txt"
echo "$TAG ($ARM) ${ENDED:-ended at G+$PLAY}$WHY (after $DUR s; G ${G:-none}, load ${LOADT:-none}, list ${LISTED:-none})" > "$R/$TAG-end.txt"
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a "fps counter" "$R/$TAG-play.log" | sed -E 's/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\1 \2 \3 \4/' > "$R/$TAG-fps.txt"
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" | head -80 > "$R/$TAG-crash.txt" 2> /dev/null
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  echo "journal $J $(stat -c '%y %s' "$J")" > "$R/$TAG-journal.txt"
  nice -n 19 grep -a "^guard\|^lazy release\|^memory (exp 0401)\|FAILED\|^learned: fault\|^reopen" "$J" | cut -c1-1200 > "$R/$TAG-guard.txt"
  nice -n 19 grep -a "^frame profile: t" "$J" | sed -n 's/^frame profile: t \([0-9.]*\) s, \([0-9.]*\) ms since the last flip; game thread inside the host \([0-9.]*\) ms.*outside \([0-9.]*\); GPU busy \([0-9.]*\) ms.*/\1 \2 \3 \4 \5/p' > "$R/$TAG-frames.txt"
else echo "no journal of this run ($J)" > "$R/$TAG-journal.txt"; : > "$R/$TAG-guard.txt"; : > "$R/$TAG-frames.txt"; fi
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC\|Killed" > "$R/$TAG-dmesg-after.txt"
S1=$(sumof "$WD/_SaveData"); echo "$(date '+%F %T') $TAG the private copy after the arm: $S1 ($([ "$S1" = "$NSUM" ] && echo unchanged || echo "the title wrote it"))" >> "$R/saves.txt"
FPSL=$(awk 'NF == 4 {n++; f += $2; s += $3; if ($4 > 100) b++; if ($4 > mx) mx = $4} END {if (s > 0) printf "%.1f flips/s over %d s, %d s with a gap over 100 ms, longest %.0f ms", f / s, s, b, mx; else printf "no fps lines"}' "$R/$TAG-fps.txt")
echo "$(cat "$R/$TAG-end.txt"); $FPSL; kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), crash lines $(grep -c . "$R/$TAG-crash.txt"), ledger lines $(grep -c '^guard: t' "$R/$TAG-guard.txt")" > "$R/$TAG-summary.txt"
sync
cat "$R/$TAG-summary.txt"
