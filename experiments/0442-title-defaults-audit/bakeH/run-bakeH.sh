#!/usr/bin/env bash
# bake H checks (2026-11-24): the first title on the host through ab442c.sh, 180 s per run, the shared bc5-mount (now host-built).
#   F: the new shared normal (function, 1 run); then R74: warm-up discarded, 3 rounds of H (the new shared lean),
#   C (the kept container-built lean 1e47486a) and J (C again: the null arm)
set -u
W=$HOME/bc5-work; X=$W/exp0442
NN=$W/kytyplus-build/src/kyty_emulator; NL=$W/kytyplus-build-lean/src/kyty_emulator; OL=$W/kytyplus-build-lean.container-1124/src/kyty_emulator
m8() { md5sum < "$1" | cut -c1-8; }
PN=$(m8 "$NN"); PL=$(m8 "$NL"); [ "$PN" = 5727b07f ] && [ "$PL" = 94a6513c ] && [ "$(m8 "$OL")" = 1e47486a ] || { echo "pins"; exit 1; }
T=$(date +%H%M)
AB_CB=$NN AB_OB=$NN AB_NB=$NN AB_PIN_C=$PN AB_PIN_O=$PN AB_PIN_N=$PN AB_WARMUP=0 AB_ROUNDS=1 AB_ARMS="F" AB_ARM_F="$NN|$PN|" \
  MEMF=hb/mem-bhf$T.txt bash "$X/ab442c.sh" "q442bhf$T" || { echo "the function run stopped"; exit 1; }
AB_CB=$NL AB_OB=$NL AB_NB=$OL AB_PIN_C=$PL AB_PIN_O=$PL AB_PIN_N=1e47486a AB_WARMUP=1 AB_ROUNDS=3 AB_ARMS="H C J" \
  AB_ARM_H="$NL|$PL|" AB_ARM_C="$OL|1e47486a|" AB_ARM_J="$OL|1e47486a|" MEMF=hb/mem-bhab$T.txt bash "$X/ab442c.sh" "q442bhab$T"
