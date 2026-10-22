#!/usr/bin/env bash
# BC5 experiment 0218: after the play, release BOX-LOCK (only if it is ours) and note the end time.
cd ~/bc5-work || exit 1
pgrep -f "kyty_emulator --game" >/dev/null && { echo "the game is still running: lock kept"; exit 1; }
# the emulator log is overwritten by the next run (exp 0210 lost its own): keep it here first
[ play-pkg-last.log -nt exp0218/start.txt ] && cp -p play-pkg-last.log exp0218/emu.log && echo "emulator log kept as exp0218/emu.log"
grep -q "play exp 0218" BOX-LOCK 2>/dev/null && rm -f BOX-LOCK && echo "BOX-LOCK released"
date +%T > exp0218/end.txt
