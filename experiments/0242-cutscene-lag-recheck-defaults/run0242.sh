#!/usr/bin/env bash
# BC5 experiment 0242: does the second title's cutscene slow motion (F259, F267) persist on the defaults of
# 2026-10-23? One scripted run of the shared build through the shortcut's own launcher (play-pkg.sh, no BC5_EMU, no
# switch set): the fixed APR read-ahead (F287/F288), the condition-variable wait (F281), reflections on (F277).
# Route: exp 0203's O2 (S1's end saves exp0196/saves-before-152617, whose slot-3 autosave lies just before a lagging
# cutscene; exp0203/o2-continue.cmd plays the menu inputs to Continue it), SECS s (default 600).
# Beside it, read-only:
#   - exp 0200's sample0200.py: the cinematic clock, the main cinematic player's clip time and debt, the box's
#     vmstat/PSI and the watched threads;
#   - exp 0220's mem0220.sh: the box's memory every 15 s.
# The clock voice's archive is journaled (KYTY_BC5_APR_FILE_JOURNAL=7cd713df) for its record-to-run delays.
# Only the emulator PID this script started is stopped. The live saves are kept aside by exp 0196's ab-restore.sh,
# put back and checked with diff -rq. Only after the top session's GRANTED; it refuses while any emulator runs
# (process names starting "kyty_emulator") or another session holds ~/bc5-work/BOX-LOCK.
# usage: run0242.sh <tag> [secs]   (on the box, from an attended SSH session; the laptop streams the kernel log)
set -u
TAG=${1:?tag}
SECS=${2:-600}
E=$HOME/bc5-work/exp0242; R=$E/raw
LOCK=$HOME/bc5-work/BOX-LOCK
SD=$HOME/bc5-work/_SaveData/PPSA03671
SAVES=$HOME/bc5-work/exp0196/saves-before-152617
CMD=$HOME/bc5-work/exp0203/o2-continue.cmd
BIN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator LOG=$HOME/bc5-work/play-pkg-last.log
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ]; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
mkdir -p "$R"
[ "$SECS" -le 1200 ] || { echo "at most 1200 s"; exit 1; }
[ -d "$SAVES" ] && [ -r "$CMD" ] || { echo "no save set $SAVES or input $CMD"; exit 1; }
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG already used in $R"; exit 1; }
echo "exp 0242 | cutscene re-check run $TAG ($SECS s, shared build, defaults; GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 4)) min" +%H:%M)" > "$LOCK"
release() { grep -q "^exp 0242 | cutscene re-check run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released $(date +%T)"; }
sleep 2
OUT=$(~/bc5-work/exp0196/ab-restore.sh "$SAVES") || { echo "$OUT"; release; exit 1; }
echo "$OUT" | tee "$R/$TAG-restore.txt"
KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
[ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; release; exit 1; }
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
cp "$CMD" "$E/op-$TAG.cmd"
{ date '+%F %T'; echo "binary $BIN $(stat -c %y "$BIN" | cut -c1-19) md5 $(md5sum "$BIN" | cut -c1-32), $SECS s, saves $SAVES, live saves kept in $KEEP"
  echo "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); KYTY_BC5_APR_READAHEAD in the environment: ${KYTY_BC5_APR_READAHEAD:-unset}"
  echo "play-pkg.sh md5 $(md5sum "$HOME/bc5-work/play-pkg.sh" | cut -c1-32), $(stat -c %y "$HOME/bc5-work/play-pkg.sh" | cut -c1-19); its switch lines:"
  grep -n "^export BC5_DIRECT_FLAT_APERTURE\|BC5_DIRECT_AMM_PRT=\|^export BC5_DIRECT_SKIP_PGM\|KYTY_BC5_APR" "$HOME/bc5-work/play-pkg.sh" | cut -c1-200
  echo "before: $(free -m | awk 'NR > 1 {printf "%s total %s used %s free %s avail %s; ", $1, $2, $3, $4, $7}')"; } > "$R/$TAG-start.txt"
setsid nohup distrobox enter ubuntu -- env -u BC5_EMU KYTY_BC5_INPUT_CMD="$E/op-$TAG.cmd" KYTY_BC5_APR_FILE_JOURNAL=7cd713df \
  "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
# No emulator ran before the launch (checked above), so the first one now is this run's; only that PID is stopped.
EP=""
for _ in $(seq 1 60); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 1; done
echo "emulator pid ${EP:-none}: $(ps -o comm=,args= -p "${EP:-1}" 2> /dev/null | cut -c1-120)" >> "$R/$TAG-start.txt"
if [ -n "$EP" ]; then
  setsid nohup nice -n 5 python3 -I "$HOME/bc5-work/exp0200/sample0200.py" "$R/$TAG-sample.txt" 20 < /dev/null > "$R/$TAG-sampler.err" 2>&1 &
  setsid nohup nice -n 10 "$HOME/bc5-work/exp0220/mem0220.sh" "$R/$TAG-mem.txt" "$EP" < /dev/null > /dev/null 2>&1 &
fi
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
grep -a "^apr journal (exp 0203)" "$R/$TAG-play-pkg.log" > "$R/$TAG-apr-journal.txt"
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
echo "$TAG: crash lines $(grep -c . "$R/$TAG-crash.txt"), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), clock-voice journal lines $(grep -c . "$R/$TAG-apr-journal.txt")" | tee "$R/$TAG-summary.txt"
