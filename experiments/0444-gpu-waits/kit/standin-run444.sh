#!/usr/bin/env bash
# BC5 exp 0444: a laptop stand-in of run444.sh (no box, no GPU). Fake HOME, a fake wait-rings that
# prints one verdict, stubs for distrobox (runs its command), pgrep (no emulator) and the kernel-log
# read (GATE_DMESG). Cases: clean (admitted, case runs, lock released), read fails (R43 refusal, exit 3),
# a GPU line on the boot (R60 refusal, exit 2), a foreign lock line (refused, the line untouched).
set -u
K=$(cd "$(dirname "$0")" && pwd); S=$(mktemp -d); FAIL=0
mkdir -p "$S/home/bc5-work/exp0444/build" "$S/bin"
printf '#!/bin/sh\necho "verdict T5 cpu-writes ctx one: AS EXPECTED"\nexit 0\n' > "$S/home/bc5-work/exp0444/build/wait-rings"
printf '#!/bin/sh\nshift 3; exec "$@"\n' > "$S/bin/distrobox"
printf '#!/bin/sh\nexit 1\n' > "$S/bin/pgrep"
printf '#!/bin/sh\necho "[ 1.0] Linux version"\necho "[ 2.0] amdgpu 0000:01:00.0: SMU ok"\n' > "$S/bin/clean"
printf '#!/bin/sh\nexit 1\n' > "$S/bin/fail"
printf '#!/bin/sh\necho "[ 9.0] amdgpu 0000:01:00.0: amdgpu: ring gfx_0.0.0 timeout"\n' > "$S/bin/gpu"
chmod +x "$S/bin/"* "$S/home/bc5-work/exp0444/build/wait-rings"
cp -r "$K" "$S/kit"; md5sum < "$S/home/bc5-work/exp0444/build/wait-rings" | cut -c1-8 > "$S/kit/PIN"
one() { # one LABEL DMESG WANT_RC WANT_LOCK
    local rc lock
    HOME="$S/home" PATH="$S/bin:$PATH" GATE_DMESG="$S/bin/$2" bash "$S/kit/run444.sh" T5 one > "$S/out" 2>&1; rc=$?
    lock=$(cat "$S/home/bc5-work/BOX-LOCK" 2> /dev/null)
    if [ "$rc" = "$3" ] && [ "$lock" = "$4" ]; then echo "PASS $1: rc $rc lock [$lock]"; else echo "FAIL $1: rc $rc (want $3) lock [$lock] (want [$4])"; tail -3 "$S/out"; FAIL=1; fi
}
one clean clean 0 ""
one readfail fail 3 ""
one gpuline gpu 2 ""
echo "busy" > "$S/home/bc5-work/BOX-LOCK"
one foreignlock clean 1 "busy"
rm -rf "$S"
[ "$FAIL" = 0 ] && echo "standin-run444: ALL PASS" || { echo "standin-run444: FAILED"; exit 1; }
