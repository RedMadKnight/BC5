#!/usr/bin/env bash
# BC5 experiment 0214: a smoke run of a shared build with the APR read-ahead on by default, through the shortcut's
# own launcher (play-pkg.sh, no BC5_EMU; BC5_LEAN=1 for the lean build) and with no KYTY_BC5_APR_READAHEAD set.
# Route: exp 0203's O2 (S1's end saves, exp0196/saves-before-152617, whose slot-3 autosave lies just before a lagging
# cutscene; exp 0203's o2-continue.cmd plays the menu inputs to Continue it), SECS seconds (default 300).
# The normal build also journals the clock voice's archive (KYTY_BC5_APR_FILE_JOURNAL=7cd713df), to check the
# read-ahead lines and the in-order completion sequence. Beside it: cpu0214.sh (APR threads' CPU, the process's RSS)
# and exp 0200's sample0200.py (the cinematic clock).
# Saves: the live saves are kept aside by exp 0196's ab-restore.sh, put back after the run and checked with diff -rq.
# Only after the top session's GRANTED; it refuses while an emulator runs or another session holds ~/bc5-work/BOX-LOCK
# (inside chain0214.sh the chain's lock line is reused). usage: run0214.sh <tag> [secs] [lean 0|1]   (on the box)
set -u
TAG=${1:?tag}
SECS=${2:-300}
LEAN=${3:-0}
E=$HOME/bc5-work/exp0214; R=$E/raw
LOCK=$HOME/bc5-work/BOX-LOCK
SD=$HOME/bc5-work/_SaveData/PPSA03671
SAVES=$HOME/bc5-work/exp0196/saves-before-152617
CMD=$HOME/bc5-work/exp0203/o2-continue.cmd
[ "$SECS" -le 1200 ] || { echo "at most 1200 s"; exit 1; }
[ -d "$SAVES" ] && [ -r "$CMD" ] || { echo "no save set $SAVES or input $CMD"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0214 |" "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
OWN=0
if [ "$LEAN" = 1 ]; then BIN=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=$HOME/bc5-work/play-pkg-lean-last.log
else BIN=$HOME/bc5-work/kytyplus-build/src/kyty_emulator LOG=$HOME/bc5-work/play-pkg-last.log; fi
sleep 2  # ab-restore.sh names its copies by time (exp 0203's 17:58:17); now unique, the pause is kept anyway
OUT=$(~/bc5-work/exp0196/ab-restore.sh "$SAVES") || { echo "$OUT"; exit 1; }
echo "$OUT" | tee "$R/$TAG-restore.txt"
KEEP=$(echo "$OUT" | sed -n 's/.*(previous saves in \(.*\))$/\1/p')
[ -d "$KEEP" ] || { echo "the live saves were not kept: stop"; exit 1; }
[ -s "$LOCK" ] || { OWN=1; echo "exp 0214 | smoke run $TAG ($SECS s, lean $LEAN; GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d "+$((SECS / 60 + 3)) min" +%H:%M)" > "$LOCK"; }
sudo -n dmesg 2> /dev/null | wc -l > "$R/$TAG-dmesg-before.txt"
cp "$CMD" "$E/op-$TAG.cmd"
{ date '+%F %T'; echo "binary $BIN $(stat -c %y "$BIN" | cut -c1-19) md5 $(md5sum "$BIN" | cut -c1-32), lean $LEAN, $SECS s, saves $SAVES, live saves kept in $KEEP"
  echo "KYTY_BC5_APR_READAHEAD in the environment: ${KYTY_BC5_APR_READAHEAD:-unset}"; } > "$R/$TAG-start.txt"
JENV="KYTY_BC5_APR_FILE_JOURNAL=7cd713df"; [ "$LEAN" = 1 ] && JENV="BC5_LEAN=1"
setsid nohup distrobox enter ubuntu -- env -u KYTY_BC5_APR_READAHEAD KYTY_BC5_INPUT_CMD="$E/op-$TAG.cmd" $JENV \
  "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null && break; sleep 1; done
setsid nohup nice -n 10 "$E/cpu0214.sh" "$R/$TAG-cpu.txt" < /dev/null > /dev/null 2>&1 &
setsid nohup nice -n 5 python3 -I "$HOME/bc5-work/exp0200/sample0200.py" "$R/$TAG-sample.txt" 20 < /dev/null > "$R/$TAG-sampler.err" 2>&1 &
T0=$(date +%s); ENDED=""
while [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  pgrep -x kyty_emulator > /dev/null || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  sleep 2
done
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator 2> /dev/null; sleep 3
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
[ "$OWN" = 1 ] && grep -q "^exp 0214 | smoke run $TAG " "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released"
# the summary: reader threads, read-ahead journal lines, in-order copies, sequence decreases, CPU and RSS
NR=$(awk '$1 == "t" && $3 ~ /^bc5-apr-r/ {print $3}' "$R/$TAG-cpu.txt" | sort -u | wc -l)
RA=$(grep -c "readahead cb .* into host memory" "$R/$TAG-apr-journal.txt")
RUNS=$(grep -c " run cb .* read file " "$R/$TAG-apr-journal.txt")
DEC=$(grep " run cb .* write addr 0x000000090adf7fe0 " "$R/$TAG-apr-journal.txt" | awk '{v = strtonum($14); if (n && v < p) d++; p = v; n++} END {print d + 0}')
echo "$TAG summary: reader threads $NR, readahead lines $RA, in-order copies $RUNS, sequence decreases $DEC, crash lines $(grep -c . "$R/$TAG-crash.txt"), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt")" | tee "$R/$TAG-summary.txt"
awk '$1 == "t" {n = $3; sub(/[0-9-]+$/, "", n); if (!($3 in a)) {a[$3] = $4; t0[$3] = $2}; b[$3] = $4; t1[$3] = $2; k[$3] = n}
     $1 == "m" {for (i = 3; i < NF; i += 2) if ($i == "VmRSS:") {r = $(i + 1); if (r > mx) mx = r; if (!mn || r < mn) mn = r; last = r}}
     END {for (x in a) {c[k[x]] += (b[x] - a[x]) / 1e9; d = t1[x] - t0[x]; if (d > dur[k[x]]) dur[k[x]] = d}
          for (g in c) printf "  %s* CPU %.1f s in %.0f s (%.2f %% of one core)\n", g, c[g], dur[g], dur[g] ? 100 * c[g] / dur[g] : 0
          printf "  VmRSS min %d, max %d, last %d MiB\n", mn / 1024, mx / 1024, last / 1024}' "$R/$TAG-cpu.txt" | tee -a "$R/$TAG-summary.txt"
