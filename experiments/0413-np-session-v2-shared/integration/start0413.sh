#!/usr/bin/env bash
# BC5 exp 0413: a start check of the integration's private build with no input (exp 0389's "lean start" and "ASTRO BOT
# start"): the emulator runs <seconds> from a private working directory, then gets SIGTERM. Pass: it is still running
# at the end, no amdgpu kernel line, no crash text in its log.
#   lean:  the lean binary through run0413p.sh's derived launcher ($N/play-pkg-0413n.sh: made by the first run0413p.sh
#          run), the words of P_WORDS, BC5_LEAN=1 BC5_LOGS=1, RT on, the save copy reset from exp 0412's named snapshot
#   astro: ASTRO BOT through a copy of ~/bc5-work/play-astro.sh with EMU, LOG and the working directory changed (a
#          private _SaveData that starts empty)
# BOX-LOCK by an atomic hard-link claim; only our exact line is removed. ulimit -c 0.
# usage (on the box): P_BIN=<binary> P_WANT=<md5> [P_WORDS=<file>] start0413.sh <tag> lean|astro <seconds> [KEY=VALUE ...]
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$X/night/saves-named; NSF=$X/night/saves-named.sum
TAG=${1:?a tag}; KIND=${2:?lean or astro}; SECS=${3:?seconds}; shift 3; EXTRA=("$@")
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
case "$SECS" in *[!0-9]* | "") echo "seconds"; exit 1 ;; esac
[ "$SECS" -ge 60 ] && [ "$SECS" -le 600 ] || { echo "60-600 s"; exit 1; }
BIN=${P_BIN:?the binary}; WANT=${P_WANT:?its md5}
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
sumof() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
mkdir -p "$R" || exit 1
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -e "$R/$TAG-end.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
[ "$(m "$BIN")" = "$WANT" ] || { echo "the binary is not $WANT: not started"; exit 1; }
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$'); [ -n "$WL" ] || { echo "no Wayland socket: not started"; exit 1; }
ENVS=(WAYLAND_DISPLAY="$WL")
case "$KIND" in
  lean)
    LAUNCH=$N/play-pkg-0413n.sh; WD=$N/wd; LOG=$N/play-last.log
    [ -x "$LAUNCH" ] && [ -d "$WD/_SaveData" ] || { echo "no derived launcher or wd (run run0413p.sh first): not started"; exit 1; }
    mapfile -t WORDS < <(grep -v "^#" "${P_WORDS:?the words file}" | grep .)
    CFG=$N/input-$TAG.cfg
    { grep -v -i "^RayTracing\.PPSA03671=\|^JobArenaFix\.PPSA03671=" "$W/input.cfg"; echo "RayTracing.PPSA03671=on"; echo "JobArenaFix.PPSA03671=on"; } > "$CFG" || exit 1
    rm -rf "$WD/_SaveData/PPSA03671" && cp -a "$NS/PPSA03671" "$WD/_SaveData/PPSA03671" || { echo "the saves could not be put in place"; exit 1; }
    [ "$(sumof "$WD/_SaveData")" = "$(cat "$NSF")" ] || { echo "the private copy does not read as the named snapshot: not started"; exit 1; }
    ENVS+=("${WORDS[@]}" KYTY_BC5_MANGOHUD=0 "BC5_EMU=$BIN" "BC5_0412N_INPUT_CONFIG=$CFG") ;;  # the lean binary strips the diagnostic words itself (BC5_LEAN constructor); the 0412 launcher refuses BC5_LEAN=1
  astro)
    LAUNCH=$N/play-astro-0413.sh; WD=$N/wda; LOG=$N/astro-last.log
    if [ ! -e "$WD" ]; then
      mkdir -p "$WD/_SaveData" || exit 1
      find "$W/exp0330/wd" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || { echo "the wd links could not be copied"; exit 1; }
    fi
    [ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] || { echo "$WD/_SaveData is not a private directory"; exit 1; }
    sed -e "s#^EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\$#EMU=$BIN  \# exp 0413: the private build#" \
        -e "s#^LOG=~/bc5-work/play-last.log\$#LOG=$LOG  \# exp 0413: own log#" \
        -e "s#^cd ~/bc5-work\$#cd $WD  \# exp 0413: the private working directory#" "$W/play-astro.sh" > "$LAUNCH" || exit 1
    [ "$(diff "$W/play-astro.sh" "$LAUNCH" | grep -c '^>')" = 3 ] || { echo "the derived ASTRO launcher is not 3 lines changed: not started"; rm -f "$LAUNCH"; exit 1; }
    grep -q '^ulimit -c 0' "$LAUNCH" || sed -i '2i ulimit -c 0  # exp 0413' "$LAUNCH"
    bash -n "$LAUNCH" && chmod +x "$LAUNCH" || exit 1 ;;
  *) echo "lean or astro"; exit 1 ;;
esac
ENVS+=("${EXTRA[@]}")
T=$(date +%Y%m%d%H%M%S)$$
LINE="exp 0413 | private start $TAG ($KIND, $SECS s) on exp0413/${WANT:0:8}, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0413s-$$.new; al=$LOCK.0413s-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
EP=""
release() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0413s-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi; }
cleanup() { if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi; release; }
trap cleanup EXIT
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
echo "$(date '+%F %T') $TAG $KIND, $SECS s, binary $BIN $WANT, launcher $(m "$LAUNCH" | cut -c1-8)" > "$R/$TAG-start.txt"
setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  [ "$(md5sum < "/proc/$EP/exe" | cut -d' ' -f1)" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the working directory is not $WD"
fi
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ENDED BY ITSELF at $(($(date +%s) - T0)) s"; break; }
  if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then ENDED="GPU: kernel amdgpu line at $(($(date +%s) - T0)) s"; break; fi
  sleep 5
done
ANON=""; [ -n "$EP" ] && [ -d "/proc/$EP" ] && ANON=$(awk '/^RssAnon/ {print $2}' "/proc/$EP/status")
cleanup; EP=""
sleep 3
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|Killed" > "$R/$TAG-dmesg-after.txt"
cp -p "$LOG" "$R/$TAG-play.log" 2> /dev/null
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" 2> /dev/null | head -80 > "$R/$TAG-crash.txt"
grep -a "\[bc5\]\|exp 04[01][0-9]" "$R/$TAG-play.log" 2> /dev/null | sort | uniq -c | sort -rn | head -40 > "$R/$TAG-lines.txt"
echo "$TAG ($KIND) ${ENDED:-PASS: ran $SECS s}; RssAnon at the end ${ANON:-?} kB; kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), crash lines $(grep -c . "$R/$TAG-crash.txt")" | tee "$R/$TAG-end.txt"
