#!/usr/bin/env bash
# BC5 exp 0438: the clean-boot chain of 2026-11-21 (boot c97d43e6), the top session's GO:
#  1. lean A/B A1+A1P+A2 (ab438o.sh: both arms the stack's lean f8c92e46, the other arm with the switch words), N1 normal 853e16e9 with A2_CHECK + probe;
#  2. one normal run INFLIGHT_NG alone, 60 s, probe (armq438.sh): the safety check;
#  3. only if 2 is clean: lean A/B INFLIGHT_NG (control vs =1), N1 normal with INFLIGHT_NG + probe.
# Each part claims its own lock; any failed part stops the chain.
set -u
K=$HOME/bc5-work/exp0438; LOG=$K/chain438.log
S=$K/stack; L=$S/lean/kyty_emulator; N=$S/normal/kyty_emulator
echo "$(date '+%F %T') chain438 start, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)" > "$LOG"
AB_CB=$L AB_OB=$L AB_NB=$N AB_PIN_C=f8c92e46 AB_PIN_O=f8c92e46 AB_PIN_N=853e16e9 \
  AB_O_WORDS="KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1" \
  AB_N_WORDS="KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1 BC5_DIRECT_TIMEOUT_PROBE=1" \
  bash $K/r438okit/ab438o.sh qa1A >> "$LOG" 2>&1; r=$?
echo "$(date +%T) part 1 rc $r" >> "$LOG"; [ $r = 0 ] || { echo "STOP after part 1" >> "$LOG"; exit 1; }
sleep 5
bash $K/stackkit/armq438.sh qng1 BC5_0438_INFLIGHT_NG=1 BC5_DIRECT_TIMEOUT_PROBE=1 >> "$LOG" 2>&1; r=$?
echo "$(date +%T) part 2 rc $r" >> "$LOG"; grep -q "RESULT qng1: CLEAN" "$LOG" || { echo "STOP after part 2 (not clean)" >> "$LOG"; exit 1; }
sleep 5
AB_CB=$L AB_OB=$L AB_NB=$N AB_PIN_C=f8c92e46 AB_PIN_O=f8c92e46 AB_PIN_N=853e16e9 \
  AB_O_WORDS="BC5_0438_INFLIGHT_NG=1" AB_N_WORDS="BC5_0438_INFLIGHT_NG=1 BC5_DIRECT_TIMEOUT_PROBE=1" \
  bash $K/r438okit/ab438o.sh qngA >> "$LOG" 2>&1; r=$?
echo "$(date +%T) part 3 rc $r" >> "$LOG"; echo "chain438 end" >> "$LOG"
