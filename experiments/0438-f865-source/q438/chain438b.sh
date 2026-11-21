#!/usr/bin/env bash
# BC5 exp 0438: the guarded gate on boot c97d43e6 (the top session's GO, 18:23): the normal 60-s safety run INFLIGHT_NG=1
# OPEN_NG=1 with the probe, then (only if clean) the lean A/B control vs both, W0 discarded, 3 pairs, a 4th if within 0.3 %.
set -u
K=$HOME/bc5-work/exp0438; LOG=$K/chain438b.log; S=$K/stack; L=$S/lean/kyty_emulator; N=$S/normal/kyty_emulator
echo "$(date '+%F %T') chain438b start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)" > "$LOG"
ARM_PIN=15707d7f bash $K/stackkit/armq438.sh qgn1 BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 BC5_DIRECT_TIMEOUT_PROBE=1 >> "$LOG" 2>&1
J=$(ls -dt $HOME/bc5-data/captures/play-* | head -1)/gc/direct.log
echo "qgn1 ng438 lines:" >> "$LOG"; grep -a "ng438" "$J" | tail -3 | cut -c1-400 >> "$LOG"
grep -q "RESULT qgn1: CLEAN" "$LOG" || { echo "STOP after the safety run (not clean)" >> "$LOG"; exit 1; }
sleep 5
AB_CB=$L AB_OB=$L AB_NB=$N AB_PIN_C=a1dfc44a AB_PIN_O=a1dfc44a AB_PIN_N=15707d7f AB_WARMUP=1 AB_PAIR4=auto \
  AB_O_WORDS="BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1" AB_N_WORDS="BC5_0438_INFLIGHT_NG=1 BC5_0438_OPEN_NG=1 BC5_DIRECT_TIMEOUT_PROBE=1" \
  bash $K/r438okit/ab438o.sh qggA >> "$LOG" 2>&1; r=$?
J=$(ls -dt $HOME/bc5-data/captures/play-* | head -1)/gc/direct.log
echo "N1 ng438 lines:" >> "$LOG"; grep -a "ng438" "$J" | tail -3 | cut -c1-400 >> "$LOG"
echo "$(date +%T) A/B rc $r; chain438b end" >> "$LOG"
