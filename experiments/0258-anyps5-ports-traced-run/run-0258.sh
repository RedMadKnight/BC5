#!/usr/bin/env bash
# BC5 experiment 0258: one scripted run of the second title in the private working directory
# ~/bc5-work/exp0258/wd (setup0258.sh), with the save-data trace on, driven by a route file through
# KYTY_BC5_INPUT_CMD. The live saves (~/bc5-work/_SaveData) are never read or written by the title;
# their checksum is taken before and after and the two are compared. Only the emulator this script
# started is stopped at the end. Adapted from exp 0194's run-0194b.sh.
# usage: ROUTE=list-load.cmd [SECS=150] [SHOTS="62 70 80 95 110 140"] [RESET=1] run-0258.sh <tag>
TAG=${1:?tag}; SECS=${SECS:-150}; SHOTS=${SHOTS:-62 70 80 95 110 140}
cd ~/bc5-work || exit 1
E=~/bc5-work/exp0258; W=$E/wd/_SaveData/PPSA03671; LIVE=~/bc5-work/_SaveData/PPSA03671
O=$E/r-$TAG; [ -e "$O" ] && { echo "$O exists (tag reused)"; exit 1; }
pgrep "^kyty_emulator" >/dev/null && { echo busy; exit 1; }
[ -s ~/bc5-work/BOX-LOCK ] && { echo "BOX-LOCK held: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
echo "exp 0258 | $TAG: traced save/list/delete on a private save copy (${ROUTE:-list-load.cmd}, $SECS s) | start $(date +%H:%M) | until ~$(date -d "+$((SECS/60+3)) min" +%H:%M 2>/dev/null)" > ~/bc5-work/BOX-LOCK
trap 'rm -f ~/bc5-work/BOX-LOCK' EXIT
manifest() { (cd "$1" 2>/dev/null && find . -type f -print0 | sort -z | xargs -0 sha256sum 2>/dev/null); }
sidecars() { echo "--- $1 ($(date +%H:%M:%S))"; ls -la --time-style=+%H:%M:%S "$W" 2>/dev/null | tail -n +2; for f in "$W"/*.blocks; do [ -f "$f" ] && echo "$(basename "$f"): $(cat "$f")"; done; }
mkdir -p "$O/shots"
[ "${RESET:-0}" = 1 ] && RESET=1 bash "$E/setup0258.sh" > "$O/setup.out" 2>&1
sync
manifest "$LIVE" > "$O/live-saves-before.sha256"
{ sidecars "private copy before the run"; } > "$O/sidecars.txt"
cp "$E/${ROUTE:-list-load.cmd}" "$O/input.cmd"
echo "${ENVX:-defaults}" > "$O/env.txt"
UP0=$(cut -d" " -f1 /proc/uptime)
setsid nohup ~/bc5-work/exp0190/shots.sh "$O/shots" $SHOTS < /dev/null > /dev/null 2>&1 &
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$O/input.cmd BC5_0194_INPUT_CONFIG=$HOME/bc5-work/exp0194/input-0194.cfg ${ENVX:-} "$E/play-pkg-0258.sh" < /dev/null > "$O/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep "^kyty_emulator" >/dev/null && break; sleep 1; done
EPID=$(pgrep -n "^kyty_emulator")
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  kill -0 "$EPID" 2>/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 2
done
J=$(ls -td ~/bc5-data/captures/play-*/gc 2>/dev/null | head -1)
[ -n "$EPID" ] && { kill "$EPID" 2>/dev/null; sleep 4; kill -9 "$EPID" 2>/dev/null; sleep 3; }
cp "$E/play-pkg-last.log" "$O/emu.log" 2>/dev/null
{ sidecars "private copy after the run"; } >> "$O/sidecars.txt"
manifest "$LIVE" > "$O/live-saves-after.sha256"
sudo -n dmesg | awk -v up0="$UP0" "{ts = substr(\$0, 2, index(\$0, \"]\") - 2) + 0; if (ts >= up0) print}" > "$O/dmesg.txt" 2>/dev/null
echo "$J" > "$O/journal-dir.txt"
echo "== $TAG (${ROUTE:-list-load.cmd}, ${ENVX:-defaults}): ${ENDED:-stopped at $SECS s}; journal $J"
if cmp -s "$O/live-saves-before.sha256" "$O/live-saves-after.sha256"; then echo "live saves: unchanged ($(sha256sum < "$O/live-saves-after.sha256" | cut -c1-16))"; else echo "LIVE SAVES CHANGED (see $O/live-saves-*.sha256)"; fi
echo "kernel: $(grep -c "page fault" "$O/dmesg.txt") fault lines, $(grep -c -i "ring .*timeout\|GPU reset" "$O/dmesg.txt") ring timeout/reset lines"
bash "$E/check0258.sh" "$TAG" | tee "$O/summary.txt"
