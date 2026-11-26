#!/usr/bin/env bash
# BC5 exp 0439 (tag sr439c, the top session's order of 11-23 ~14:00): the pass census's slot in one script.
# v2 (11-23 ~15:00): each copied frame also gets its own picture (display.raw, the decompressed display surface at its
# flip; sr439cread.py --display makes display.png): the label of the frame.
#   1. prep439d.sh (the kit of slot439ph plus mksr439c in the unit and mksr439cbe in the backend; sr0439c.hpp in both
#      include dirs), pinned below from the laptop stand-in chain; box439b2.sh into d2/priv11 (private).
#   2. three scripted runs (st439.sh, fresh saves, no pad input; v2: four arms each, 60, 80, 100, 120 s), each with BC5_0439_PASS_DUMP=~/bc5-data/priv/passes and
#      two arms (BC5_0439_PASS_AT=60,100: seconds after the first flip), shots every 3 s from 60 to 135 s for the
#      black/good label of each armed frame (sr439cread.py --classify; the shots' times next to the captures' meta
#      times). Run 1 with BC5_0439_PASS_MEC=0 (copies on the GFX ring only: the MEC's DMA_DATA is unverified), runs 2
#      and 3 with the compute rings too, only when run 1 left no GPU kernel line.
#   A GPU kernel line after any run stops the series (st439.sh reports the count; this script checks the journal).
# Run on the box, on the top session's word, as one named unit:
#   systemd-run --user --unit=x439sc --collect -p RuntimeMaxSec=3600 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439sc.sh > slot439sc.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2
stop() { echo "slot439sc STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; } # st439.sh's count, no sudo
cd "$K" || exit 1
date "+start %F %T"
bash prep439d.sh > sc-prep.txt 2>&1 || { tail -5 sc-prep.txt; stop prep; }
tail -3 sc-prep.txt | cut -c1-1400
NEW_PINS="ajm.cpp=44e01c8b atrac9_decoder.h=402d5d10 bc5LleAgc.cpp=ce2b5824 controller.cpp=f0408c33 cw0439.hpp=9f1436d3 dc0439.hpp=c05cca6d dm0439.hpp=f2bf23e1 fp0439.hpp=9594ccf0 libAmpr.cpp=f5c78bef libVideoDec2.cpp=a315ac6d main.cpp=6b8e4411 pw0439.hpp=3b482094 pthread.cpp=f1ff5b6e sr0439b.hpp=f294f3fd sr0439c.hpp=2bf80130 switch_defaults.hpp=24f28ef3 tc0439.hpp=82404073 vf0439.hpp=6f589325 videoDec2Decoder.cpp=c63e3b5c videoOut.cpp=11f5e977 window.cpp=ee925d6c"
BE_PINS="src/direct.cpp=4c5ed838 src/full_state.cpp=c49ae21f src/policy.cpp=e8541e0a include/bc5/ib_chain.hpp=11df8b8f include/bc5/ds0439.hpp=c2b318af include/bc5/pw0439.hpp=3b482094 include/bc5/dk0439.hpp=565f3d80 include/bc5/sr0439c.hpp=2bf80130"
BASE_PINS="patch 8a9ed0cf normal fd8e44e1 lean 1e47486a archive ba25f31c swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS BC5_0439_PIECE_HOLD BC5_0439_DCC_UNCOMPRESSED BC5_0439_PASS_DUMP BC5_0439_PASS_AT BC5_0439_PASS_MB BC5_0439_PASS_WINDOW BC5_0439_PASS_STRIDE BC5_0439_PASS_MEC"
(cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp" \
    EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv11" bash box439b2.sh > "$K/sc-build.txt" 2>&1) || { grep -a "STOP\|build rc\|error:" "$K/sc-build.txt" | tail -6; stop build; }
grep -a "build rc\|private normal\|shared after" "$K/sc-build.txt" | tail -4 | cut -c1-300
P=$(m8 "$D/priv11/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv11/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
echo "binary $P"
PD=$HOME/bc5-data/priv/passes; mkdir -p "$PD" && chmod 700 "$PD"
SHOTS="60 63 66 69 72 75 78 81 84 87 90 93 96 99 102 105 108 111 114 117 120 123 126 129 132 135"
: > sc-shots.txt
for i in 1 2 3; do
    g0=$(gl)
    MEC=1; [ $i = 1 ] && MEC=0
    out=$(ST_MORE="BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_AT=60,80,100,120 BC5_0439_PASS_MEC=$MEC" ST_SHOTS="$SHOTS" ST_BOUND=150 bash st439.sh "$P" 2>&1 | tail -1)
    echo "run $i (PASS_MEC=$MEC): $out"
    SH=$(echo "$out" | sed -n 's/.*shots in \(.*\)$/\1/p')
    [ -n "$SH" ] && stat -c '%Y %n' "$SH"/*.png >> sc-shots.txt 2> /dev/null
    L=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1)
    grep -a "tag sr439c" "$L/play-last.log" 2> /dev/null | cut -c1-400 | tail -12
    [ $i = 1 ] && bash rowcheck439.sh "$L/play-last.log" "$D/new/switch_defaults.hpp"
    [ "$(gl)" = "$g0" ] || stop "a GPU kernel line in run $i ($g0 -> $(gl)): no further run"
    sleep 5
done
ls -l "$PD" | tail -12
du -sh "$PD"
date "+end %F %T"
