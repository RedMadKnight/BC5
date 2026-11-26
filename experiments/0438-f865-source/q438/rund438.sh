#!/usr/bin/env bash
# BC5 exp 0438: the two IB-dump runs the top session approved (2026-11-21), as ONE named systemd --user unit (LESSONS R73):
# wait (bounded 60 min) for an empty BOX-LOCK and no emulator / bc5-mount, then the display check (R72), then
#   D1  the full set + INFLIGHT_NG/OPEN_NG/HELD_EARLY (it stalls, it does not reboot), BC5_DIRECT_IB_DUMP of every buffer;
#   D2  a clean arm without SUBMITQ (A1 A1P A2 only), the same dump, for the order to compare.
# Each 60 s on the first title through armq438.sh (its own lock, the reset count, the fault record), journal=min (the launcher's
# default), the timeout probe. The dumps go to each run's private capture directory (~/bc5-data/captures/play-*/gc).
set -u
K=$HOME/bc5-work/exp0438; LOG=$K/rund438.log; L=$HOME/bc5-work/BOX-LOCK
M=$(cut -c1-8 "$K/stack/normal/binary.md5")
DUMP="BC5_DIRECT_IB_DUMP=0:400000:0:900"
echo "$(date '+%F %T') rund438 start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), stack normal $M" > "$LOG"
t0=$(date +%s)
while [ $(( $(date +%s) - t0 )) -lt 3600 ]; do
    if [ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null && ! pgrep -x bc5-mount > /dev/null; then break; fi
    sleep 20
done
[ ! -s "$L" ] && ! pgrep -x kyty_emulator > /dev/null || { echo "no free slot within 60 min" >> "$LOG"; exit 1; }
. "$K/display438.inc"
for arm in D1 D2; do
    display_check || { echo "STOP before $arm: $DISP (R72)" >> "$LOG"; exit 1; }
    echo "$arm: $DISP" >> "$LOG"
    if [ $arm = D1 ]; then
        W="BC5_0438_SUBMITQ=1 KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1 BC5_0438_R438_LWM=1 BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 BC5_0438_HELD_EARLY=1"
    else
        W="KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1"
    fi
    # shellcheck disable=SC2086
    ARM_PIN=$M bash "$K/stackkit/armq438.sh" qd$arm $W $DUMP BC5_DIRECT_TIMEOUT_PROBE=1 >> "$LOG" 2>&1
    echo "$(date +%T) $arm: dumps $(ls "$(ls -dt $HOME/bc5-data/captures/play-* | head -1)/gc" | grep -c '^ib-') in $(ls -dt $HOME/bc5-data/captures/play-* | head -1)" >> "$LOG"
    grep -q "RESULT qd$arm: NOT CLEAN" "$LOG" && grep -q "reset count changed\|A RING RESET FAILED" "$LOG" && { echo "STOP after $arm (a GPU line)" >> "$LOG"; exit 1; }
    sleep 5
done
echo "$(date +%T) rund438 end" >> "$LOG"
