#!/usr/bin/env bash
# BC5 exp 0388: the maintainer's own play of the fight with the job-arena fix off and one bounded wait on, no time limit.
# The top session starts it on the box when the box is free. It uses the normal launcher, his saves and his input.cfg,
# which it does not change; only this start's environment differs. It stops when he closes the game.
# usage: play0388.sh [F|J]   F: the wait of the second cycle (5 of 5); J: the job-paired wait, if the third cycle holds
set -u
ARM=${1:-F}
BIN=$HOME/bc5-work/exp0388/kyty_emulator
case "$ARM" in
    F) WAIT=KYTY_BC5_0388_PUSH_UNTIL_RETURN_US=500 ;;
    J) WAIT=KYTY_BC5_0388_PUSH_UNTIL_TARGET_US=2000 ;;
    *) echo "play0388: the arm is F or J"; exit 1 ;;
esac
pgrep '^kyty_emulator' > /dev/null && { echo "play0388: an emulator runs"; exit 1; }
[ ! -s "$HOME/bc5-work/BOX-LOCK" ] || { echo "play0388: the box is locked: $(cat "$HOME/bc5-work/BOX-LOCK")"; exit 1; }
[ -x "$BIN" ] || { echo "play0388: no $BIN"; exit 1; }
echo "play0388: arm $ARM, binary $(md5sum < "$BIN" | cut -c1-8), JobArenaFix off, RT as in input.cfg"
exec distrobox enter ubuntu -- env BC5_EMU="$BIN" KYTY_BC5_JOB_ARENA_FIX=0 KYTY_BC5_0388_TRACE=1 "$WAIT" "$HOME/bc5-work/play-pkg.sh"
