#!/usr/bin/env bash
# BC5 exp 0429: the tests of the R swap form before the swap, on the private rs builds (each step its own lock line):
# ASTRO BOT lean 200 s with the build defaults (R by kSoft), the second title lean check (8/8 Hi, 0 refusals), the
# normal check. Stops at the first failure.
set -u
ulimit -c 0
E=$HOME/bc5-work/exp0429
echo "== $(date +%T) a429R1 ASTRO BOT lean 200 s (rs lean)"
(cd ~/bc5-work/exp0431 && XBIN=$E/rs/lean/kyty_emulator bash astro0431.sh 200 a429R1:x:D) > $E/smoke-a429R1.out 2>&1; tail -4 $E/smoke-a429R1.out
grep -q "a429R1: PASS" $E/smoke-a429R1.out || { echo "a429R1 not a PASS: stopped"; exit 1; }
sleep 10
echo "== $(date +%T) h429K19 second title lean check (rs lean)"
(cd ~/bc5-work/exp0413/n && CHECK_DIR=$E/rs/lean RRMODE=3 bash $E/check0429l.sh h429K19) > $E/check-h429K19.out 2>&1; grep "check h429K19\|PASS: ran\|FAIL" $E/check-h429K19.out | cut -c1-240
grep -q "check h429K19: PASS" $E/check-h429K19.out || { echo "h429K19 not a PASS: stopped"; exit 1; }
sleep 10
echo "== $(date +%T) h429K20 normal check (rs normal)"
CHECK_DIR=$E/rs/normal RRMODE=3 bash $E/check0429r.sh h429K20 > $E/check-h429K20.out 2>&1; grep "check h429K20\|CLASS" $E/check-h429K20.out | cut -c1-240
grep -q "check h429K20: PASS" $E/check-h429K20.out || { echo "h429K20 not a PASS: stopped"; exit 1; }
echo "smoke0429r ended $(date +%T): all PASS"
