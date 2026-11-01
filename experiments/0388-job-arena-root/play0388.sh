#!/usr/bin/env bash
# BC5 exp 0388: the maintainer's own play of the fight with the job-arena fix off and one bounded wait on, no time limit.
# The top session starts it on the box when the box is free. It uses the normal launcher, his saves and his input.cfg,
# which it does not change; only this start's environment differs. It stops when he closes the game.
# usage: [BC5_0388_LEARNED=<file>] play0388.sh [F|J]   F: the wait of the second cycle (5 of 5); J: the job-paired wait, if the third cycle holds
# BC5_0388_LEARNED: the learned list of this start. play-pkg.sh sets the list itself, so a private copy of it gets that one
# line; the shared launcher and the shared list stay as they are, and a fault in this play is learned into <file> only.
# BC5_0388_MEMORY=1: the memory cycle's binary exp0388/m/kyty_emulator with the zero skip on the moving list, shared canary
# slices and scans of the other eager heaps. Each has its own switch; empty turns one off:
# BC5_0388_ZERO_LIST=<file>, BC5_0388_SLICES=<n>, BC5_0388_SCAN_AT=<s,s,...>.
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
LAUNCH=$HOME/bc5-work/play-pkg.sh
LIST="shared list"
MEM=()
MEMTXT=""
if [ "${BC5_0388_MEMORY:-0}" = 1 ]; then
    M=$HOME/bc5-work/exp0388/m
    BIN=$M/kyty_emulator
    [ -x "$BIN" ] || { echo "play0388: no $BIN"; exit 1; }
    Z=${BC5_0388_ZERO_LIST-$M/zero-list-moving.txt}
    S=${BC5_0388_SLICES-}
    A=${BC5_0388_SCAN_AT-300,600,900,1200,1800}
    if [ -n "$Z" ]; then
        [ -s "$Z" ] || { echo "play0388: no zero list at $Z"; exit 1; }
        MEM+=("BC5_DIRECT_ZERO_SKIP=$Z")
        MEMTXT=", zero list $(md5sum < "$Z" | cut -c1-8)"
        [ -z "$S" ] || { MEM+=("BC5_DIRECT_ZERO_SLICES=$S"); MEMTXT="$MEMTXT, $S slices"; }
    fi
    if [ -n "$A" ]; then
        N=$(sed -n 's/^export BC5_DIRECT_EAGER_NAMES="\([^"]*\)".*/\1/p' "$LAUNCH" | tr ',' '\n' | grep -vx AMM | paste -sd, -)
        [ -n "$N" ] || { echo "play0388: no eager names in the launcher"; exit 1; }
        MEM+=("BC5_DIRECT_ZERO_NAMES=$N" "BC5_DIRECT_ZEROSCAN_AT=$A" "BC5_DIRECT_ZEROSCAN_OUT=$M/zero-scan-play.txt")
        MEMTXT="$MEMTXT, scans at $A"
    fi
fi
if [ -n "${BC5_0388_LEARNED:-}" ]; then
    [ -s "$BC5_0388_LEARNED" ] || { echo "play0388: no list at $BC5_0388_LEARNED"; exit 1; }
    case "$BC5_0388_LEARNED" in "$HOME"/bc5-work/exp0388/*) ;; *) echo "play0388: the list must be private"; exit 1 ;; esac
    NEW=$HOME/bc5-work/exp0388/play-pkg-learned.sh
    awk -v want='export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt' -v new="export BC5_DIRECT_LEARNED=$BC5_0388_LEARNED"         '$0 == want { print new; n++; next } { print } END { exit n == 1 ? 0 : 1 }' "$LAUNCH" > "$NEW" || { echo "play0388: the launcher's list line was not found once"; exit 1; }
    grep -Fxq "export BC5_DIRECT_LEARNED=$BC5_0388_LEARNED" "$NEW" || { echo "play0388: the private launcher lacks the list"; exit 1; }
    chmod +x "$NEW"
    LAUNCH=$NEW
    LIST="private list $BC5_0388_LEARNED $(md5sum < "$BC5_0388_LEARNED" | cut -c1-8), $(wc -l < "$BC5_0388_LEARNED") windows"
fi
echo "play0388: arm $ARM, binary $(md5sum < "$BIN" | cut -c1-8), JobArenaFix off, RT as in input.cfg, $LIST$MEMTXT"
exec distrobox enter ubuntu -- env BC5_EMU="$BIN" KYTY_BC5_JOB_ARENA_FIX=0 KYTY_BC5_0388_TRACE=1 "$WAIT" "${MEM[@]}" "$LAUNCH"
