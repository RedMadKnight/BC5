#!/usr/bin/env bash
# BC5 exp 0432: the lean smokes after int0432 (the host-work removal in the shared builds), as exp 0429's smoke0429.sh:
# The first title lean 200 s (exp 0431's t1_0431.sh, the build's defaults, D), then the second title lean 300 s by time
# (exp 0428's lean0428.sh: RT on, input.cfg as shared). Each step takes and releases its own BOX-LOCK line. Stops at
# the first run that is not a PASS or at ~/bc5-work/exp0432/STOP.
# usage (on the box, detached): bash ~/bc5-work/exp0432/kit/smoke0432.sh
set -u
ulimit -c 0
S=$HOME/bc5-work/exp0432
echo "== $(date +%T) a432S1 the first title lean 200 s ($(md5sum < ~/bc5-work/kytyplus-build-lean/src/kyty_emulator | cut -c1-8))"
(cd ~/bc5-work/exp0431 && bash t1_0431.sh 200 a432S1:l:D) | tee "$S/smoke-a432S1.out"
grep -q "a432S1: PASS" "$S/smoke-a432S1.out" || { echo "a432S1 not a PASS: stopped"; exit 1; }
[ -e "$S/STOP" ] && exit 1
echo "== $(date +%T) l432S2 second title lean 300 s"
cd ~/bc5-work/exp0413/n && bash ~/bc5-work/exp0428/lean0428.sh l432S2
grep -q "PASS: ran" ~/bc5-work/exp0413/n/raw/l432S2-end.txt || { echo "l432S2 not a PASS: stopped"; exit 1; }
echo "oom lines since boot: $(sudo -n dmesg | grep -c oom-killer); amdgpu timeout/reset lines: $(sudo -n dmesg | grep -ci 'amdgpu.*\(timeout\|reset\)')"
echo "smoke0432 ended $(date +%T): both PASS"
