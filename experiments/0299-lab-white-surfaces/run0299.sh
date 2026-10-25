#!/usr/bin/env bash
# BC5 experiment 0299 (exp 0194's run-0194b.sh, for the lab): one scripted run of the second title from the lab save
# (setup0299.sh's saves-lab-1001, reset into the private working directory ~/bc5-work/exp0299/wd before the run)
# through play-pkg-0299.sh (today's play-pkg.sh in that directory). The maintainer's own saves are never read or
# written. ROUTE=<input file in exp0299>, ENVX=<switches>, SHOTS=<seconds after the emulator starts>. Only the emulator
# this script started is stopped at the end.
# usage: ENVX="<switches>" ROUTE=continue.cmd SHOTS="..." run0299.sh <tag> [secs]
TAG=$1; SECS=${2:-260}; SHOTS=${SHOTS:-100 120 140 160 180 200 220 240}
E=$HOME/bc5-work/exp0299
cd ~/bc5-work || exit 1
pgrep "^kyty_emulator" > /dev/null && { echo busy; exit 1; }
W=$E/wd/_SaveData/PPSA03671
diff -rq "$E/saves-lab-1001" "$W" > /dev/null 2>&1 || { rm -rf "$W" && cp -a "$E/saves-lab-1001" "$W"; echo "private save copy reset to saves-lab-1001"; }
sync
O=$E/r-$TAG; mkdir -p "$O/shots"
echo "${ENVX:-defaults}" > "$O/env.txt"
cp "$E/${ROUTE:-continue.cmd}" "$O/input.cmd"
UP0=$(cut -d" " -f1 /proc/uptime)
setsid nohup ~/bc5-work/exp0190/shots.sh "$O/shots" $SHOTS < /dev/null > /dev/null 2>&1 &
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$O/input.cmd BC5_0299_INPUT_CONFIG=$HOME/bc5-work/exp0194/input-0194.cfg ${ENVX:-} "$E/play-pkg-0299.sh" < /dev/null > "$O/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null && break; sleep 1; done
EPID=$(pgrep -n -x kyty_emulator)
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  kill -0 "$EPID" 2>/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 2
done
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)
cp "$E/play-last.log" "$O/emu.log" 2>/dev/null
[ -n "$EPID" ] && { kill "$EPID" 2>/dev/null; sleep 4; kill -9 "$EPID" 2>/dev/null; sleep 3; }
sudo -n dmesg | awk -v up0="$UP0" "{ts = substr(\$0, 2, index(\$0, \"]\") - 2) + 0; if (ts >= up0) print}" > "$O/dmesg.txt"
echo "$J" > "$O/journal-dir.txt"
echo "== $TAG (${ENVX:-defaults}): ${ENDED:-stopped at $SECS s}; journal $J"
echo "kernel: $(grep -c "page fault" "$O/dmesg.txt") fault lines, $(grep -c -i "ring .*timeout\|GPU reset" "$O/dmesg.txt") ring timeout/reset lines"
echo "journal: $(grep -a -c TIMEOUT "$J/direct.log") fence timeouts; $(wc -l < "$J/direct.log") lines"
