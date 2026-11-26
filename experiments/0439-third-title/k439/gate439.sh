#!/usr/bin/env bash
# BC5 exp 0439 (tag gt439): the clean-boot gate for every exp-0439 unit on a clean boot (LESSONS R55, R60; R43: no data
# is not zero, the flaw top found in exp 0438's guard). Reads the kernel log once, refuses when the read fails or comes
# back empty, refuses when it holds an amdgpu/drm timeout or reset line, admits otherwise. bc5-gpu-watch's start line
# ("watching the kernel log for amdgpu resets ...", on every boot, seen 11-22 at 31 s) is not a GPU event and is left out.
#   gate439.sh            exit 0 admitted, 2 refused (a GPU kernel line), 3 refused (the read failed or was empty)
#   GATE_DMESG="cmd"      the read command (default: sudo -n dmesg), for the stand-in dry run
set -u
CMD=${GATE_DMESG:-sudo -n dmesg}
OUT=$($CMD 2> /dev/null)
RC=$?
if [ $RC -ne 0 ] || [ -z "$OUT" ]; then
    echo "gate439: REFUSED: the kernel log read failed (rc $RC, $(printf '%s' "$OUT" | grep -c .) lines): no data is not zero (R43)"
    exit 3
fi
PAT='amdgpu.*\(timeout\|reset\)\|drm.*\(timeout\|reset\)'
HIT=$(printf '%s\n' "$OUT" | grep -a "$PAT" | grep -a -v 'bc5-gpu-watch: watching the kernel log' | grep -a -v -e '] Kernel command line: ' -e '] Command line: ')
K=$(printf '%s' "$HIT" | grep -a -c .)
N=$(printf '%s\n' "$OUT" | grep -c .)
if [ "$K" != 0 ]; then
    echo "gate439: REFUSED: $K amdgpu/drm timeout or reset lines in $N kernel log lines on this boot (R55, R60)"
    printf '%s\n' "$HIT" | head -2
    exit 2
fi
echo "gate439: admitted: 0 amdgpu/drm timeout or reset lines in $N kernel log lines"
exit 0
