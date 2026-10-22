#!/usr/bin/env bash
# BC5 experiment 0194: one scripted run of the second title to the night lake (the maintainer's pad recording of
# session 2026-10-22 10:11, route-1011.cmd, replayed through KYTY_BC5_INPUT_CMD), with the switches in ENVX over
# play-pkg.sh's defaults, screenshots at fixed seconds, then kill. The saves are copied to save-backup-<tag> at the start and put back
# before and after (the run may autosave).
# usage: ENVX="<switches>" SHOTS="120 130 ..." run-0194.sh <tag> [secs]
TAG=$1; SECS=${2:-175}; SHOTS=${SHOTS:-115 125 135 145 155 165}
cd ~/bc5-work
SD=_SaveData/PPSA03671; BK=exp0194/save-backup-$TAG
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*; do [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null && echo "saves as in $BK" || echo "SAVES DIFFER from $BK"
}
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
[ -e "$BK" ] && { echo "$BK exists"; exit 1; }
cp -a "$SD" "$BK" && restore
sync
O=exp0194/r-$TAG; mkdir -p "$O/shots"
echo "${ENVX:-defaults}" > "$O/env.txt"
cp exp0194/${ROUTE:-route-1011-t41.cmd} "$O/input.cmd"
UP0=$(cut -d" " -f1 /proc/uptime)
setsid nohup exp0190/shots.sh "$O/shots" $SHOTS < /dev/null > /dev/null 2>&1 &
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/$O/input.cmd ${ENVX:-} ~/bc5-work/play-pkg.sh < /dev/null > "$O/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
EPID=$(pgrep -n -x kyty_emulator)  # only this emulator is stopped at the end
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  kill -0 "$EPID" 2>/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 2
done
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)
cp play-pkg-last.log "$O/emu.log"
[ -n "$EPID" ] && { kill "$EPID" 2>/dev/null; sleep 4; kill -9 "$EPID" 2>/dev/null; sleep 3; }
if pgrep -x kyty_emulator >/dev/null; then echo "ANOTHER EMULATOR IS RUNNING: saves NOT restored (backup $BK)"; else restore; fi
sudo -n dmesg | awk -v up0="$UP0" "{ts = substr(\$0, 2, index(\$0, \"]\") - 2) + 0; if (ts >= up0) print}" > "$O/dmesg.txt"
echo "$J" > "$O/journal-dir.txt"
echo "== $TAG (${ENVX:-defaults}): ${ENDED:-stopped at $SECS s}; journal $J"
echo "kernel: $(grep -c "page fault" "$O/dmesg.txt") fault lines, $(grep -c -i "ring .*timeout\|GPU reset" "$O/dmesg.txt") ring timeout/reset lines"
echo "journal: $(grep -a -c TIMEOUT "$J/direct.log") fence timeouts; $(wc -l < "$J/direct.log") lines"
ls "$O/shots" "$J"
