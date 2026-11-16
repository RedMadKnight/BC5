#!/usr/bin/env bash
# BC5 exp 0425 (2026-11-16, the top session's GO for one slot): CHAIN_SET=p3rep, then CHAIN_SET=sched, each a
# chain0425.sh with its own BOX-LOCK line. The second starts only if the first ended without a STOP line, no STOP file
# exists, the lock is free and no emulator runs.
# usage (on the box, detached, in ~/bc5-work/exp0425): CHAIN_TARGET_OK=1 bash both0425.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
say() { echo "both0425 $(date +%T): $*"; }
CHAIN_SET=p3rep bash "$HERE/chain0425.sh" > "$HERE/chain0425-p3rep.out" 2>&1
if grep -q '^chain0425 [0-9:]*: STOP' "$HERE/chain0425-p3rep.out" || ! grep -q '^chain0425 [0-9:]*: ended$' "$HERE/chain0425-p3rep.out"; then
  say "p3rep stopped or did not end cleanly: sched NOT started"; exit 1
fi
[ -e "$HERE/STOP" ] && { say "STOP file: sched NOT started"; exit 1; }
sleep 15
pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs: sched NOT started"; exit 1; }
[ -s "$HOME/bc5-work/BOX-LOCK" ] && { say "the lock is held: sched NOT started"; exit 1; }
CHAIN_SET=sched bash "$HERE/chain0425.sh" > "$HERE/chain0425-sched.out" 2>&1
say "both sets done"
