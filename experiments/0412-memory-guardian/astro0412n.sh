#!/usr/bin/env bash
# BC5 exp 0412: one unattended ASTRO BOT run for the leak rate (the top session's order for the night of 2026-11-10/11:
# "the two ASTRO BOT runs, capture off / on, 10 min each with the sampler"). It runs play-astro-guard-0412.sh <off|on>
# (the shared build 4d2b1b1d through exp 0412's private launcher copy, the sampler sampler0412b.sh and the fuse), adds
# the watchdog wd0412.sh, and ends the emulator after <seconds> with SIGTERM. No input is sent: the title stays where it
# starts. The desktop's Wayland socket is passed on (wayland-1 this boot; a run over ssh has none).
# BOX-LOCK by an atomic hard-link claim; only our exact line is removed.
# usage (on the box): astro0412n.sh <tag> off|on|evlog|evcap|evplain <seconds>   (ev*: the events-cap build, play-astro-ev-0412.sh)
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; N=$X/night; R=$N/raw; LOCK=$W/BOX-LOCK
TAG=${1:?a tag}; ARM=${2:?off or on}; SECS=${3:?seconds}
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
case "$ARM" in off | on) WRAP=$X/play-astro-guard-0412.sh; WARM=$ARM; LASTLOG=$X/astro-last.log ;;
  evlog | evcap | evplain) WRAP=$X/play-astro-ev-0412.sh; WARM=${ARM#ev}; LASTLOG=$X/astro-ev-last.log ;;   # the events-cap build (ev412)
  *) echo "the arm is off, on, evlog, evcap or evplain"; exit 1 ;; esac
case "$SECS" in *[!0-9]* | "") echo "seconds, please"; exit 1 ;; esac
[ "$SECS" -ge 60 ] && [ "$SECS" -le 2400 ] || { echo "60-2400 s"; exit 1; }
mkdir -p "$R" || exit 1
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
pgrep -x bc5-mount > /dev/null && { echo "a bc5-mount is running: not started"; exit 1; }
[ -e "$R/$TAG-end.txt" ] && { echo "tag $TAG already used: not started"; exit 1; }
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$'); [ -n "$WL" ] || { echo "no Wayland socket: not started"; exit 1; }
bash "$WRAP" "$WARM" dry > "$R/$TAG-dry.txt" 2>&1 && grep -q '^dry: sampler pinned' "$R/$TAG-dry.txt" && grep -q '^dry: fuse pinned' "$R/$TAG-dry.txt" || { echo "the wrapper's dry run failed: $(tail -1 "$R/$TAG-dry.txt")"; exit 1; }
T=$(date +%Y%m%d%H%M%S)$$
LINE="guard exp 0412 | night astro $TAG (capture $ARM, $SECS s), ASTRO BOT on the shared build, unattended, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0412a-$$.new; al=$LOCK.0412a-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
printf '%s\n' "guard exp 0412 | claimed: night astro $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
EP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412a-$$.rel"; mv -fT "$LOCK.0412a-$$.rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: night astro $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
S0=$(ls "$X/sampler/" 2> /dev/null | wc -l)
WAYLAND_DISPLAY=$WL setsid nohup bash "$WRAP" "$WARM" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe"), capture word $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -x 'PLAY_CAPTURE=.*' || echo "PLAY_CAPTURE unset"), journal dir $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep '^BC5_GC_DUMP_DIR=' || echo none)" > "$R/$TAG-start.txt"
  setsid nohup bash "$X/wd0412.sh" "$EP" "$R/$TAG-watchdog.txt" 300 60 > /dev/null 2>&1 < /dev/null &
  while [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    sleep 5
  done
fi
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
for _ in $(seq 1 60); do pgrep -f "play-astro-0412.sh|play-astro-ev0412.sh" > /dev/null || break; sleep 1; done
sleep 4
SF=$(ls -t "$X/sampler/"astro-*-capture-"$ARM".txt 2> /dev/null | head -1)
[ -n "$SF" ] && [ "$(ls "$X/sampler/" | wc -l)" -gt "$S0" ] && cp -p "$SF" "$R/$TAG-sampler.txt"
cp -p "$LASTLOG" "$R/$TAG-play.log" 2> /dev/null
grep -a "exp 0412 events" "$R/$TAG-play.log" 2> /dev/null | cut -c1-300 > "$R/$TAG-events.txt"
grep -a "fps counter" "$R/$TAG-play.log" 2> /dev/null | sed -E 's/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\1 \2 \3 \4/' > "$R/$TAG-fps.txt"
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|Killed" > "$R/$TAG-dmesg-after.txt"
WHY=""; grep -q "KILLED" "$R/$TAG-watchdog.txt" 2> /dev/null && WHY="; THE WATCHDOG KILLED IT"
echo "$TAG (astro capture $ARM) ${ENDED:-ended at $SECS s}$WHY (after $DUR s); sampler lines $(grep -vc '^#' "$R/$TAG-sampler.txt" 2> /dev/null); kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"); $(tail -1 "$X/fuse.log" 2> /dev/null | cut -c1-200)" > "$R/$TAG-end.txt"
sync
cat "$R/$TAG-end.txt"
