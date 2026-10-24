#!/usr/bin/env bash
# BC5 experiment 0291: one scripted run of exp 0291's test binary through the second title's launcher (play-pkg.sh with
# BC5_EMU) with KYTY_BC5_VIDEOOUT_REPORT=<report> ("-" leaves it unset: the host's answer, 1 today). Route: exp 0203's O2
# (exp0196/saves-before-152617 and exp0203/o2-continue.cmd), SECS s (default 300), as exp 0242's run0242.sh: the live
# saves kept aside by exp 0196's ab-restore.sh, put back and checked with diff -rq; only the PID started is stopped;
# exp 0220's mem0220.sh beside it. Afterwards the run's "bc5 videoout:" lines go to raw/<tag>-videoout.txt.
# It refuses while any emulator runs or any BOX-LOCK is held. usage: run0291.sh <tag> <report|-> [secs]   (on the box)
set -u
TAG=${1:?tag}; REPORT=${2:?report or -}; SECS=${3:-300}
E=$HOME/bc5-work/exp0291; R=$E/raw
LOCK=$HOME/bc5-work/BOX-LOCK
SD=$HOME/bc5-work/_SaveData/PPSA03671
SAVES=$HOME/bc5-work/exp0196/saves-before-152617
CMD=$HOME/bc5-work/exp0203/o2-continue.cmd
BIN=$E/bin/kyty_emulator LOG=$HOME/bc5-work/play-pkg-last.log
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -x "$BIN" ] || { echo "no test binary $BIN"; exit 1; }
mkdir -p "$R"
[ "$SECS" -le 1200 ] || { echo "at most 1200 s"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used in $R"; exit 1; }
echo "exp 0291 | run $TAG (VIDEOOUT_REPORT $REPORT, $SECS s; GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 4)) min" +%H:%M)" > "$LOCK"
release() { grep -q "^exp 0291 | run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released $(date +%T)"; }
sleep 2
OUT=$(~/bc5-work/exp0196/ab-restore.sh "$SAVES") || { echo "$OUT"; release; exit 1; }
echo "$OUT" | tee "$R/$TAG-restore.txt"
KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
[ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; release; exit 1; }
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
cp "$CMD" "$E/op-$TAG.cmd"
REPORT_ENV=""; [ "$REPORT" != "-" ] && REPORT_ENV="KYTY_BC5_VIDEOOUT_REPORT=$REPORT"
{ date '+%F %T'; echo "binary $BIN md5 $(md5sum "$BIN" | cut -c1-32), report ${REPORT_ENV:-unset}, $SECS s, saves $SAVES, live saves kept in $KEEP"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); play-pkg.sh md5 $(md5sum "$HOME/bc5-work/play-pkg.sh" | cut -c1-32)"
  echo "before: $(free -m | awk 'NR > 1 {printf "%s total %s used %s free %s avail %s; ", $1, $2, $3, $4, $7}')"; } > "$R/$TAG-start.txt"
setsid nohup distrobox enter ubuntu -- env BC5_EMU="$BIN" KYTY_BC5_INPUT_CMD="$E/op-$TAG.cmd" $REPORT_ENV \
  "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
EP=""
for _ in $(seq 1 60); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 1; done
echo "emulator pid ${EP:-none}: $(ps -o comm=,args= -p "${EP:-1}" 2> /dev/null | cut -c1-120)" >> "$R/$TAG-start.txt"
[ -n "$EP" ] && setsid nohup nice -n 10 "$HOME/bc5-work/exp0220/mem0220.sh" "$R/$TAG-mem.txt" "$EP" < /dev/null > /dev/null 2>&1 &
T0=$(date +%s); ENDED=""
[ -n "$EP" ] || ENDED="no emulator started"
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  sleep 2
done
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
sleep 3
echo "$TAG ${ENDED:-stopped at $SECS s}" | tee "$R/$TAG-end.txt"
cp -p "$LOG" "$R/$TAG-play-pkg.log"
grep -a "^bc5 videoout:" "$R/$TAG-play-pkg.log" > "$R/$TAG-videoout.txt"
grep -a -m5 "Access violation\|Segmentation\|Aborted\|terminate called" "$R/$TAG-play-pkg.log" > "$R/$TAG-crash.txt"
J=$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
echo "$J $(stat -c '%y %s' "$J" 2> /dev/null)" > "$R/$TAG-journal-path.txt"
N=$(cat "$R/$TAG-dmesg-before.txt")
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung" > "$R/$TAG-dmesg-after.txt"
sleep 2
~/bc5-work/exp0196/ab-restore.sh "$KEEP" | tee "$R/$TAG-restore-back.txt"
if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then
  echo "NESTED SAVE COPY in $KEEP or $SD: the live saves need checking by hand" | tee -a "$R/$TAG-restore-back.txt"
elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" | tee -a "$R/$TAG-restore-back.txt"
else echo "LIVE SAVES DIFFER from $KEEP" | tee -a "$R/$TAG-restore-back.txt"; fi
release
echo "$TAG: crash lines $(grep -c . "$R/$TAG-crash.txt"), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), videoout lines $(grep -c . "$R/$TAG-videoout.txt")"
cut -c1-220 "$R/$TAG-videoout.txt" | head -12
