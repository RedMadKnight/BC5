#!/usr/bin/env bash
# exp 0442 run 7 (bake 1c+1d swapped, the top session 19:46): the function checks on the first title.
#   L: new shared lean, M: new shared normal; both with KYTY_BC5_RT=0 (the gone-words report: once in normal, none in lean)
#   and the input configuration a COPY of his (shared input.cfg + his first-title title store) with RayTracing.TITLE1B=off
#   appended to the title file. His files are only read (md5 before and after).
set -u
W=$HOME/bc5-work; X=$W/exp0442; C=$X/cfg1d
NL=$W/kytyplus-build-lean/src/kyty_emulator; NN=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$NL" | cut -c1-8); MN=$(md5sum < "$NN" | cut -c1-8)
his() { md5sum "$W/input.cfg" "$W/menu/titles/TITLE1B/input.cfg" "$W/menu/titles/TITLE1B/window" 2>/dev/null | cut -c1-8 | tr '\n' ' '; }
H0=$(his)
rm -rf "$C"; mkdir -p "$C/menu/titles/TITLE1B" || exit 1
cp "$W/input.cfg" "$C/input.cfg" && cp "$W/menu/titles/TITLE1B/input.cfg" "$W/menu/titles/TITLE1B/window" "$C/menu/titles/TITLE1B/" || exit 1
echo "RayTracing.TITLE1B=off" >> "$C/menu/titles/TITLE1B/input.cfg"
C0=$(md5sum "$C/input.cfg" "$C/menu/titles/TITLE1B/input.cfg" | cut -c1-8 | tr '\n' ' ')
echo "run7: his files [$H0], the copy [$C0] (title file with RayTracing.TITLE1B=off)"
WORDS="KYTY_BC5_RT=0 KYTY_BC5_INPUT_CONFIG=$C/input.cfg KYTY_BC5_MENU_DIR=$C/menu"
AB_CB=$NL AB_OB=$NL AB_NB=$NN AB_PIN_C=$ML AB_PIN_O=$ML AB_PIN_N=$MN AB_WARMUP=0 AB_ROUNDS=1 AB_ARMS="L M" \
  AB_ARM_L="$NL|$ML|$WORDS" AB_ARM_M="$NN|$MN|$WORDS" MEMF=ab-mem-r7.txt bash "$X/ab442c.sh" "q442f7$(date +%H%M)"
echo "run7: his files after [$(his)] (before [$H0]); the copy after [$(md5sum "$C/input.cfg" "$C/menu/titles/TITLE1B/input.cfg" | cut -c1-8 | tr '\n' ' ')] (before [$C0])"
