#!/usr/bin/env bash
# BC5 exp 0438: run B (the maintainer's word of 2026-11-21, relayed by the top session), as ONE named systemd --user unit
# (LESSONS R73). Waits (bounded 60 min) until the BOX-LOCK is empty and no emulator / bc5-mount runs; then builds the
# stack unit 0751ec42 privately (boxstack438.sh, CPU only); then, after the display check (LESSONS R72), one 60-s the first
# title run of the full set with INFLIGHT_NG=1 OPEN_NG=1 HELD_EARLY=1 (armq438.sh: its own lock, the reset count, the
# fault record), journal=min (the launcher's default), the timeout probe. Predicted clean. The run without HELD_EARLY
# is NOT part of this unit (it needs the top session's word).
set -u
K=$HOME/bc5-work/exp0438; LOG=$K/runb438.log; L=$HOME/bc5-work/BOX-LOCK
echo "$(date '+%F %T') runb438 start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)" > "$LOG"
t0=$(date +%s)
while [ $(( $(date +%s) - t0 )) -lt 3600 ]; do
    if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null && ! pgrep -x bc5-mount > /dev/null; then break; fi
    sleep 20
done
[ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null || { echo "no free slot within 60 min" >> "$LOG"; exit 1; }
echo "$(date +%T) slot free; building" >> "$LOG"
( cd "$K/stackkit" && nice -n 19 ionice -c 3 bash boxstack438.sh build ) >> "$LOG" 2>&1 || { echo "BUILD FAILED" >> "$LOG"; exit 1; }
M=$(cut -c1-8 "$K/stack/normal/binary.md5")
. "$K/display438.inc"; display_check || { echo "STOP: $DISP (R72)" >> "$LOG"; exit 1; }
echo "$DISP" >> "$LOG"
ARM_PIN=$M bash "$K/stackkit/armq438.sh" qrB1 BC5_0438_SUBMITQ=1 KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1 \
  BC5_0438_R438_LWM=1 BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 BC5_0438_HELD_EARLY=1 BC5_DIRECT_TIMEOUT_PROBE=1 >> "$LOG" 2>&1
echo "$(date +%T) runb438 end (arm rc $?)" >> "$LOG"
