#!/usr/bin/env bash
# BC5 exp 0438: the bake candidate's check on boot c97d43e6 (the top session's decision, 2026-11-21): one normal 60-s run
# of the exact bake normal (switches at their defaults: on), probe; then the lean A/B of the exact bake lean against the
# current shared lean 3a20b974: W0 discarded, 3 pairs alternating, 140 s; N1 the bake normal with the probe.
set -u
K=$HOME/bc5-work/exp0438; LOG=$K/chain438c.log; P=$K/bake438b-priv
echo "$(date '+%F %T') chain438c start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)" > "$LOG"
ARM_BIN=$P/normal/kyty_emulator ARM_PIN=87f2e1cf bash $K/stackkit/armq438.sh qbk1 BC5_DIRECT_TIMEOUT_PROBE=1 >> "$LOG" 2>&1
grep -q "RESULT qbk1: CLEAN" "$LOG" || { echo "STOP after the normal run (not clean)" >> "$LOG"; exit 1; }
sleep 5
AB_CB=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator AB_PIN_C=3a20b974 AB_OB=$P/lean/kyty_emulator AB_PIN_O=2761e911 \
  AB_NB=$P/normal/kyty_emulator AB_PIN_N=87f2e1cf AB_WARMUP=1 AB_N_WORDS="BC5_DIRECT_TIMEOUT_PROBE=1" \
  bash $K/r438okit/ab438o.sh qbkA >> "$LOG" 2>&1; r=$?
J=$(ls -dt $HOME/bc5-data/captures/play-* | head -1)/gc/direct.log
echo "N1 ng438 lines:" >> "$LOG"; grep -a "ng438 (exp" "$J" | tail -2 | cut -c1-400 >> "$LOG"
echo "$(date +%T) A/B rc $r; chain438c end" >> "$LOG"
