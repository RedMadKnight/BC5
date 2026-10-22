#!/usr/bin/env bash
# BC5 (experiment 0203): the second title's New Game opening by script, with no one at the pad. It uses exp
# 0180/0187's route (start screen, slot list, down twice to the empty slot 3, then the challenge level) and runs
# exp 0203's test binary with KYTY_BC5_APR_FILE_JOURNAL=<files> (default 7cd713df, the clock voice's archive), the
# AJM, AudioOut2 and APR traces (filtered), and exp 0200's sampler, for SECS seconds (default 600; at most 20 min
# by the top session's rule of 15:44).
# Saves:
#   - the live saves are kept aside by exp 0196's ab-restore.sh, and save-backup-0180-0953 (slot 3 empty) is put
#     in (opening-run.sh itself would overwrite the live saves);
#   - after the run the kept live saves are put back, checked with diff -rq, and the run's saves kept in turn.
# EXTRA_ENV="<VAR=value ...>" adds switches to the run (e.g. KYTY_BC5_APR_READAHEAD=4 for run O3).
# Other starts: SAVES=<save set> puts that set in instead of save-backup-0180-0953, and CMD=<input file> plays that
# KYTY_BC5_INPUT_CMD file instead of the opening route (e.g. run O2: S1's own end saves, whose slot-3 autosave of
# 15:22:36 lies just before the second lagging cutscene, and S1's menu inputs to Continue it).
# Only after the top session's GRANTED; it refuses while an emulator runs or ~/bc5-work/BOX-LOCK is held, and
# writes and removes its own lock line. usage: run0203-opening.sh <tag> [secs] [files]   (on the box, from SSH)
set -u
TAG=${1:?tag}
SECS=${2:-600}
FILES=${3:-7cd713df}
E=$HOME/bc5-work/exp0203; R=$E/raw
BIN=$E/kyty_emulator
LOCK=$HOME/bc5-work/BOX-LOCK
SD=$HOME/bc5-work/_SaveData/PPSA03671
[ "$SECS" -le 1200 ] || { echo "at most 1200 s"; exit 1; }
[ -x "$BIN" ] || { echo "no binary $BIN"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
SAVES=${SAVES:-$HOME/bc5-work/save-backup-0180-0953}
[ -d "$SAVES" ] || { echo "no save set $SAVES"; exit 1; }
# ab-restore.sh names its copy saves-before-<HHMMSS>; two calls in one second (the end of one run and the start
# of the next, 17:58:17) put the second copy inside the first, and the run after it restored the wrong set.
sleep 2
OUT=$(~/bc5-work/exp0196/ab-restore.sh "$SAVES") || { echo "$OUT"; exit 1; }
echo "$OUT" | tee "$R/$TAG-restore.txt"
KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
[ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; exit 1; }
echo "exp 0203 | scripted opening $TAG ($SECS s, journal $FILES; GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 3)) min" +%H:%M)" > "$LOCK"
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
{ date '+%F %T'; echo "binary $BIN $(stat -c %y "$BIN" | cut -c1-19), KYTY_BC5_APR_FILE_JOURNAL=$FILES, $SECS s, live saves kept in $KEEP"; } > "$R/$TAG-start.txt"
if [ -n "${CMD:-}" ]; then cp "$CMD" "$E/op-$TAG.cmd"
else printf 'wait 85000\npress cross\nwait 20000\npress down\nwait 800\npress down\nwait 800\npress cross\nwait 30000\npress cross\nwait 8000\npress cross\n' > "$E/op-$TAG.cmd"; fi
echo "saves $SAVES, extra env ${EXTRA_ENV:-none}, input $(tr '\n' ' ' < "$E/op-$TAG.cmd")" >> "$R/$TAG-start.txt"
CNT=$(nm "$BIN" 2> /dev/null | awk '/g_ajm_next_instance/ {print $1; exit}')
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD="$E/op-$TAG.cmd" BC5_EMU="$E/emu0203.sh" EMU_TS_BIN="$BIN" \
  EXP0203_TAG="$TAG" EXP0200_AJM_COUNTER="${CNT:-0}" KYTY_BC5_APR_FILE_JOURNAL="$FILES" KYTY_BC5_AJM_TRACE=1 \
  KYTY_BC5_AMM_TRACE=1 KYTY_BC5_AUDIO2_TRACE=1 ${EXTRA_ENV:-} "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null && break; sleep 1; done
T0=$(date +%s); ENDED=""
while [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  pgrep -x kyty_emulator > /dev/null || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  sleep 2
done
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator 2> /dev/null; sleep 3
echo "$TAG ${ENDED:-stopped at $SECS s}" | tee "$R/$TAG-end.txt"
cp -p ~/bc5-work/play-pkg-last.log "$R/$TAG-play-pkg.log"
grep -a "^apr journal (exp 0203)" "$R/$TAG-play-pkg.log" > "$R/$TAG-apr-journal.txt"
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
echo "$J" > "$R/$TAG-journal-path.txt"
dd if="$J" iflag=direct bs=4M 2> /dev/null | grep -a "^frame profile: t \|TIMEOUT" > "$R/$TAG-frames.txt"
N=$(cat "$R/$TAG-dmesg-before.txt")
sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung" > "$R/$TAG-dmesg-after.txt"
sleep 2
~/bc5-work/exp0196/ab-restore.sh "$KEEP" | tee "$R/$TAG-restore-back.txt"
if [ -e "$KEEP/PPSA03671" ] || [ -e "$SD/PPSA03671" ]; then
  echo "NESTED SAVE COPY in $KEEP or $SD: the live saves need checking by hand" | tee -a "$R/$TAG-restore-back.txt"
elif diff -rq "$KEEP" "$SD" > /dev/null; then echo "live saves back and identical to $KEEP" | tee -a "$R/$TAG-restore-back.txt"
else echo "LIVE SAVES DIFFER from $KEEP" | tee -a "$R/$TAG-restore-back.txt"; fi
grep -q "^exp 0203 | scripted opening $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
wc -l "$R/$TAG-apr-journal.txt" "$R/$TAG-frames.txt" "$R/$TAG-dmesg-after.txt"
