#!/usr/bin/env bash
# BC5 exp 0431: the smokes after int0431 (shared normal 6044be08, lean d239d4bf), no way-2 words anywhere (the defaults):
# ASTRO BOT lean 200 s, the second title lean 300 s (exp 0428 lean0428.sh: RT on, JobArenaFix as the shared input.cfg),
# then ASTRO BOT normal 480 s (the long run; w428c shows the defaults). Stops at the first failure or ~/bc5-work/exp0431/STOP.
set -u
ulimit -c 0
cd ~/bc5-work/exp0431 || exit 1
echo "== $(date +%T) a431S1 ASTRO lean"
bash astro0431.sh 200 a431S1:l:D || exit 1
grep -q "a431S1: PASS" astro-S.log 2>/dev/null
[ -e STOP ] && exit 1
echo "== $(date +%T) l431S2 second title lean"
cd ~/bc5-work/exp0413/n && bash ~/bc5-work/exp0428/lean0428.sh l431S2; cd ~/bc5-work/exp0431
grep -q "PASS: ran" ~/bc5-work/exp0413/n/raw/l431S2-end.txt || { echo "l431S2 not a PASS: stopped"; exit 1; }
[ -e STOP ] && exit 1
echo "== $(date +%T) a431S3 ASTRO normal 480 s"
SHOTS="60 120 180 240 300 360 420 470" bash astro0431.sh 480 a431S3:n:D
echo "smoke0431 ended $(date +%T)"
