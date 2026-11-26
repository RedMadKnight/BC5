#!/usr/bin/env bash
# BC5 experiment 0210: after the play, release BOX-LOCK (only if it is ours) and note the end time.
cd ~/bc5-work || exit 1
pgrep -f "kyty_emulator --game" >/dev/null && { echo "the game is still running: lock kept"; exit 1; }
grep -q "long play exp 0210" BOX-LOCK 2>/dev/null && rm -f BOX-LOCK && echo "BOX-LOCK released"
date +%T > exp0210/end.txt
