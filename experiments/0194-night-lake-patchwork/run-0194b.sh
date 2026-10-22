#!/usr/bin/env bash
# BC5 experiment 0194: one scripted run of the second title from the maintainer's night-lake save (slot 3, 11:51-11:52),
# in a private working directory ~/bc5-work/exp0194/wd (its own _SaveData = a copy of ~/bc5-work/saves-lake-1153; every
# other entry a symlink into ~/bc5-work) through play-pkg-0194.sh (play-pkg.sh with that working directory). The
# maintainer's own saves are never read or written. ROUTE=<input file in exp0194>, ENVX=<switches>, SHOTS=<seconds>.
# Only the emulator this script started is stopped at the end.
# usage: ENVX="<switches>" ROUTE=load-default.cmd SHOTS="..." run-0194b.sh <tag> [secs]
TAG=$1; SECS=${2:-140}; SHOTS=${SHOTS:-80 90 100 110 120 130}
cd ~/bc5-work
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
W=exp0194/wd/_SaveData/PPSA03671
diff -rq saves-lake-1153 "$W" > /dev/null || { rm -rf "$W" && cp -a saves-lake-1153 "$W"; echo "private save copy reset to saves-lake-1153"; }
sync
O=exp0194/r-$TAG; mkdir -p "$O/shots"
echo "${ENVX:-defaults}" > "$O/env.txt"
cp "exp0194/${ROUTE:-load-default.cmd}" "$O/input.cmd"
UP0=$(cut -d" " -f1 /proc/uptime)
setsid nohup exp0190/shots.sh "$O/shots" $SHOTS < /dev/null > /dev/null 2>&1 &
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/$O/input.cmd ${ENVX:-} ~/bc5-work/exp0194/play-pkg-0194.sh < /dev/null > "$O/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
EPID=$(pgrep -n -x kyty_emulator)
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  kill -0 "$EPID" 2>/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 2
done
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)
cp play-pkg-last.log "$O/emu.log"
[ -n "$EPID" ] && { kill "$EPID" 2>/dev/null; sleep 4; kill -9 "$EPID" 2>/dev/null; sleep 3; }
sudo -n dmesg | awk -v up0="$UP0" "{ts = substr(\$0, 2, index(\$0, \"]\") - 2) + 0; if (ts >= up0) print}" > "$O/dmesg.txt"
echo "$J" > "$O/journal-dir.txt"
echo "== $TAG (${ENVX:-defaults}): ${ENDED:-stopped at $SECS s}; journal $J"
echo "kernel: $(grep -c "page fault" "$O/dmesg.txt") fault lines, $(grep -c -i "ring .*timeout\|GPU reset" "$O/dmesg.txt") ring timeout/reset lines"
echo "journal: $(grep -a -c TIMEOUT "$J/direct.log") fence timeouts; $(wc -l < "$J/direct.log") lines"
