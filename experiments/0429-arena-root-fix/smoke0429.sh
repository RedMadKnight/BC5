#!/usr/bin/env bash
# BC5 exp 0429: the lean smokes after int0429 (the JobArenaFix removal in the shared builds), as exp 0431's smoke0431.sh:
# ASTRO BOT lean 200 s (exp 0431's astro0431.sh, the build's defaults, D), then the second title lean 300 s (exp 0428's
# lean0428.sh: RT on, input.cfg as shared, now without its JobArenaFix line). Each step takes and releases its own
# BOX-LOCK line. Stops at the first run that is not a PASS or at ~/bc5-work/exp0429/STOP.
# usage (on the box, detached): bash ~/bc5-work/exp0429/smoke0429.sh
set -u
ulimit -c 0
S=$HOME/bc5-work/exp0429
echo "== $(date +%T) a429S1 ASTRO BOT lean 200 s"
(cd ~/bc5-work/exp0431 && bash astro0431.sh 200 a429S1:l:D) | tee "$S/smoke-a429S1.out"
grep -q "a429S1: PASS" "$S/smoke-a429S1.out" || { echo "a429S1 not a PASS: stopped"; exit 1; }
[ -e "$S/STOP" ] && exit 1
echo "== $(date +%T) l429S2 second title lean 300 s"
cd ~/bc5-work/exp0413/n && bash ~/bc5-work/exp0428/lean0428.sh l429S2
grep -q "PASS: ran" ~/bc5-work/exp0413/n/raw/l429S2-end.txt || { echo "l429S2 not a PASS: stopped"; exit 1; }
echo "smoke0429 ended $(date +%T): both PASS"
