#!/usr/bin/env bash
# BC5 exp 0164: how fast the running title's logs grow over $1 seconds (default 10):
# the direct-path journal of the current capture (BC5_GC_DUMP_DIR from play-pkg-last.log),
# the emulator's stderr log, and the number of stderr lines in that window.
S=${1:-10}
D=$(grep -o 'BC5_GC_DUMP_DIR=[^ ]*' ~/bc5-work/play-pkg-last.log | head -1 | cut -d= -f2)
J="$D/direct.log"; L=~/bc5-work/play-pkg-last.log
j0=$(stat -c %s "$J" 2>/dev/null || echo 0); l0=$(stat -c %s "$L"); n0=$(wc -l < "$L")
sleep "$S"
j1=$(stat -c %s "$J" 2>/dev/null || echo 0); l1=$(stat -c %s "$L"); n1=$(wc -l < "$L")
echo "$(date +%T) over ${S}s: direct.log +$((j1-j0)) B, stderr log +$((l1-l0)) B (+$((n1-n0)) lines); journal=$J"
