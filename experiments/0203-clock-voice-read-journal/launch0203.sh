#!/usr/bin/env bash
# BC5 (experiment 0203): one measured play session for the maintainer from ~/bc5-work/saves-pre-1136 (slot 3), as
# exp 0200's launch0200.sh: the saves are swapped by exp 0196's ab-restore.sh (the current ones kept aside), the
# normal play-pkg.sh runs exp 0203's test binary through emu0203.sh with
#   KYTY_BC5_APR_FILE_JOURNAL=<files> (default 7cd713df, the clock voice's archive; exp 0200), the AJM and
#   AudioOut2 traces and KYTY_BC5_AMM_TRACE=1 (all filtered), and exp 0200's sampler.
# Only after the top session's "GRANTED" for this BOX REQUEST; it refuses while an emulator runs or
# ~/bc5-work/BOX-LOCK is held, and writes its own lock line. Afterwards: after0203.sh <tag>.
# usage: launch0203.sh <tag> [files]      (run on the box, from SSH; the maintainer must be at the pad)
set -u
TAG=${1:?tag}
FILES=${2:-7cd713df}
E=$HOME/bc5-work/exp0203
BIN=${EXP0203_BIN:-$E/kyty_emulator}
[ -x "$BIN" ] || { echo "no binary $BIN"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
LOCK=$HOME/bc5-work/BOX-LOCK
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
OUT=$(~/bc5-work/exp0196/ab-restore.sh) || { echo "$OUT"; exit 1; }
echo "$OUT" | tee "$E/raw/$TAG-restore.txt"
echo "exp 0203 | maintainer play $TAG from saves-pre-1136 (launch0203.sh, journal $FILES) | start $(date +%H:%M) | until ~$(date -d '+15 min' +%H:%M)" > "$LOCK"
sudo -n dmesg 2> /dev/null | wc -l > "$E/raw/$TAG-dmesg-before.txt"
{ date '+%F %T'; echo "binary $BIN $(stat -c %y "$BIN" | cut -c1-19), KYTY_BC5_APR_FILE_JOURNAL=$FILES"; } > "$E/raw/$TAG-start.txt"
CNT=$(nm "$BIN" 2> /dev/null | awk '/g_ajm_next_instance/ {print $1; exit}')
setsid nohup distrobox enter ubuntu -- env BC5_EMU="$E/emu0203.sh" EMU_TS_BIN="$BIN" EXP0203_TAG="$TAG" \
  EXP0200_AJM_COUNTER="${CNT:-0}" KYTY_BC5_APR_FILE_JOURNAL="$FILES" KYTY_BC5_AJM_TRACE=1 KYTY_BC5_AMM_TRACE=1 \
  KYTY_BC5_AUDIO2_TRACE=1 "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$E/raw/$TAG-launch.out" 2>&1 &
echo "started $TAG: $(tr '\n' ' ' < "$E/raw/$TAG-start.txt")"
