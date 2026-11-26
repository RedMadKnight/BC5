#!/usr/bin/env bash
# exp 0442 run 6 (bake 1c swapped, the top session 18:00): post-swap smoke of the new shared lean (L) and normal (M), one
# run each; then one discarded warm-up (W0, the old lean) and C (the kept copy of the old lean 05fd749d) against N (the
# new shared lean) in 3 rotating rounds: C N / N C / C N.
set -u
W=$HOME/bc5-work; X=$W/exp0442
OL=$X/swap/kyty_emulator.lean.before-0442; NL=$W/kytyplus-build-lean/src/kyty_emulator; NN=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$NL" | cut -c1-8); MN=$(md5sum < "$NN" | cut -c1-8); MO=$(md5sum < "$OL" | cut -c1-8)
[ "$MO" = 05fd749d ] || { echo "run6: the kept old lean is $MO, not 05fd749d"; exit 1; }
while [ "$(date +%H%M)" -lt 1804 ]; do sleep 5; done
echo "run6 smoke: lean $ML normal $MN"
AB_CB=$NL AB_OB=$NL AB_NB=$NN AB_PIN_C=$ML AB_PIN_O=$ML AB_PIN_N=$MN AB_WARMUP=0 AB_ROUNDS=1 AB_ARMS="L M" AB_ARM_L="$NL|$ML|" AB_ARM_M="$NN|$MN|" \
  MEMF=ab-mem-r6s.txt bash "$X/ab442c.sh" "q442s6$(date +%H%M)" || { echo "run6: smoke stopped"; exit 1; }
grep -q "other kernel lines [1-9]" "$X/r6.out" && { echo "run6: a kernel line in the smoke: A/B not started"; exit 1; }
echo "run6 A/B: C old lean $MO, N new lean $ML"
AB_CB=$OL AB_OB=$NL AB_NB=$NL AB_PIN_C=$MO AB_PIN_O=$ML AB_PIN_N=$ML AB_WARMUP=1 AB_ROUNDS=3 AB_ARMS="C N" AB_ARM_C="$OL|$MO|" AB_ARM_N="$NL|$ML|" \
  MEMF=ab-mem-r6.txt bash "$X/ab442c.sh" "q442r6$(date +%H%M)"
