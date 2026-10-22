#!/usr/bin/env bash
# BC5 (experiment 0200): one measured play session for the maintainer, from the save before the cutscenes.
# 1. Puts ~/bc5-work/saves-pre-1136 (slot 3, the autosave of 11:03) into the title's saves with exp 0196's
#    ab-restore.sh, which keeps the current saves in ~/bc5-work/exp0196/saves-before-<time>.
# 2. Records the kernel log's length, then starts the second title on the maintainer's display through the
#    normal play-pkg.sh (its skips, TF ring, journal, pad recorder) with emu0200.sh as BC5_EMU, running
#    exp 0200's test binary (~/bc5-work/exp0200/kyty_emulator: the shared build plus patch_0200.diff) with
#    KYTY_BC5_AJM_UNIQUE_IDS=<mode>, and three light traces: KYTY_BC5_AJM_TRACE (decoder jobs, into the index),
#    KYTY_BC5_AUDIO2_TRACE (per second) and KYTY_BC5_AMM_TRACE=1 (the APR submissions and reads, filtered into
#    raw/<tag>-amm.txt).
#    mode: log (default; the old ids, each reuse of a live id journaled), 1 (live ids skipped, the fix), 0 (off).
# It refuses while an emulator runs or ~/bc5-work/BOX-LOCK is held, and writes its own line there.
# Afterwards: after0200.sh <tag> collects the logs, puts the maintainer's saves back and releases the lock.
# usage: launch0200.sh <tag> [log|1|0]      (run on the box, from SSH; the maintainer must be at the pad)
set -u
TAG=${1:?tag}
MODE=${2:-log}
E=$HOME/bc5-work/exp0200
BIN=${EXP0200_BIN:-$E/kyty_emulator}
case "$MODE" in log | 1 | 0) ;; *) echo "mode is log, 1 or 0"; exit 1 ;; esac
[ -x "$BIN" ] || { echo "no binary $BIN"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
LOCK=$HOME/bc5-work/BOX-LOCK  # the sessions' box lock (top session's coordination note, 2026-10-22)
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
OUT=$(~/bc5-work/exp0196/ab-restore.sh) || { echo "$OUT"; exit 1; }
echo "$OUT" | tee "$E/raw/$TAG-restore.txt"
echo "exp 0200 | maintainer play $TAG from saves-pre-1136 (launch0200.sh, ids $MODE) | start $(date +%H:%M) | until ~$(date -d '+15 min' +%H:%M)" > "$LOCK"
sudo -n dmesg 2> /dev/null | wc -l > "$E/raw/$TAG-dmesg-before.txt"
{ date '+%F %T'; echo "binary $BIN $(stat -c %y "$BIN" | cut -c1-19), KYTY_BC5_AJM_UNIQUE_IDS=$MODE"; } > "$E/raw/$TAG-start.txt"
# The AJM instance counter's offset in the binary, for the sampler (exp 0200 result 5).
CNT=$(nm "$BIN" 2> /dev/null | awk '/g_ajm_next_instance/ {print $1; exit}')
setsid nohup distrobox enter ubuntu -- env BC5_EMU="$E/emu0200.sh" EMU_TS_BIN="$BIN" EXP0200_TAG="$TAG" \
  EXP0200_AJM_COUNTER="${CNT:-0}" KYTY_BC5_AJM_UNIQUE_IDS="$MODE" KYTY_BC5_AJM_TRACE=1 KYTY_BC5_AMM_TRACE=1 \
  KYTY_BC5_AUDIO2_TRACE=1 "$HOME/bc5-work/play-pkg.sh" < /dev/null > "$E/raw/$TAG-launch.out" 2>&1 &
echo "started $TAG: $(tr '\n' ' ' < "$E/raw/$TAG-start.txt")"
