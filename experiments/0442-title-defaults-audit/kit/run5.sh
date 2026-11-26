#!/usr/bin/env bash
# exp 0442 run 5 (the top session, 2026-11-22 16:20): the null private lean first (box0442n.sh: the private build method on
# the shared sources, lean only, priv0), then 4 arms x 3 rotating rounds (C B G N / B G N C / G N C B):
#   C shared lean 05fd749d; B bake 1b lean b0ca5133; G B with the three G4 rows off by their words;
#   N the null private lean, or, when it is byte-identical to the shared lean, A = B with only APR_PARALLEL off.
# One named unit; nothing reads the box from outside while it runs.
set -u
W=$HOME/bc5-work; X=$W/exp0442
cd "$X/kitN" || exit 1
BE_PINS="$(cat be_pins.txt)" bash box0442n.sh > "$X/box0442n.out" 2>&1
rc=$?; echo "box0442n rc $rc" >> "$X/box0442n.out"
[ "$rc" = 0 ] || exit "$rc"
SL=$W/kytyplus-build-lean/src/kyty_emulator; PB=$X/priv4/lean/kyty_emulator; PN=$X/priv0/lean/kyty_emulator
MN=$(md5sum < "$PN" | cut -c1-8)
G4="KYTY_BC5_APR_PARALLEL=0 BC5_DIRECT_MEC_INDIRECT=0 BC5_DIRECT_REMEMBER_UNMAPPED=0"
export AB_CB=$SL AB_OB=$PB AB_NB=$PB AB_PIN_C=05fd749d AB_PIN_O=b0ca5133 AB_PIN_N=b0ca5133 AB_WARMUP=0 AB_ROUNDS=3
export AB_ARM_C="$SL|05fd749d|" AB_ARM_B="$PB|b0ca5133|" AB_ARM_G="$PB|b0ca5133|$G4"
if cmp -s "$PN" "$SL"; then
    echo "run5: the null lean $MN is byte-identical to the shared lean: arm N replaced by A (B with APR_PARALLEL off)"
    export AB_ARMS="C B G A" AB_ARM_A="$PB|b0ca5133|KYTY_BC5_APR_PARALLEL=0"
else
    echo "run5: the null lean $MN differs from the shared lean 05fd749d: arm N runs it"
    export AB_ARMS="C B G N" AB_ARM_N="$PN|$MN|"
fi
while [ "$(date +%H%M)" -lt 1633 ]; do sleep 5; done # the top session: no measured run before 16:33 box clock
[ -s "$W/BOX-LOCK" ] && { echo "run5: BOX-LOCK holds a line: A/B not started"; exit 1; }
MEMF=ab-mem-r5.txt bash "$X/ab442c.sh" "q442r5$(date +%H%M)"
