#!/usr/bin/env bash
# BC5 exp 0438: Q30 on the first title (the top session's order, 2026-11-21 22:0x): ONE 180-s DIAGNOSIS run of the SHARED
# normal build (patch 589ef163: A1, A1P, A2 and the gate on by default) with the cpy438 LD_PRELOAD shim (every host copy
# of 256 KiB or more with its callers) and prof0438.sh PROF_MODE=all beside it (every thread, cpu-clock), as one named
# systemd --user unit (LESSONS R73): wait for an empty BOX-LOCK, the display check (R72), start0413g.sh (its own lock
# claim, the reset count, the kernel-line stop), journal=min (the launcher's default). A normal build with a shim and a
# profiler: no figure here is a speed measurement.
set -u
W=$HOME/bc5-work; K=$W/exp0438; N=$W/exp0413/n; R=$N/raw; L=$W/BOX-LOCK; LOG=$K/runq30.log; T=q30a
NB=$W/kytyplus-build/src/kyty_emulator; NM=$(md5sum < "$NB" | cut -d' ' -f1)
echo "$(date '+%F %T') runq30 start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), shared normal ${NM:0:8}" > "$LOG"
[ "${NM:0:8}" = 30546370 ] || { echo "the shared normal is not 30546370" >> "$LOG"; exit 1; }
t0=$(date +%s)
while [ $(( $(date +%s) - t0 )) -lt 3600 ]; do
    if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null && ! pgrep -x bc5-mount > /dev/null; then break; fi
    sleep 15
done
[ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null || { echo "no free slot within 60 min" >> "$LOG"; exit 1; }
. "$K/display438.inc"; display_check || { echo "STOP: $DISP (R72)" >> "$LOG"; exit 1; }
echo "$DISP" >> "$LOG"
mkdir -p "$R"
( for _ in $(seq 1 90); do p=$(pgrep -n -x kyty_emulator) && break; sleep 2; done
  [ -n "${p:-}" ] || exit 0
  sleep 30
  PROF_MODE=all bash "$K/kit/prof0438.sh" "$p" "$R/$T-prof" 120 > "$R/$T-prof.log" 2>&1 ) &
PP=$!
(cd "$N" && P_BIN=$NB P_WANT=$NM bash ./start0413g.sh "$T" t1 180 "LD_PRELOAD=$K/cpy/cpy438.so" "CPY438_OUT=$R/$T-cpy" BC5_FAULT_RECORD=1) > "$R/$T-runner.txt" 2>&1
echo "$(date +%T) run: $(tail -1 "$R/$T-runner.txt")" >> "$LOG"
wait "$PP" 2> /dev/null
echo "prof: $(tail -2 "$R/$T-prof.log" | tr '\n' ' ')" >> "$LOG"
echo "cpy files: $(ls "$R" | grep -c "^$T-cpy")" >> "$LOG"
echo "$(date +%T) runq30 end" >> "$LOG"
