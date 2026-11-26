#!/usr/bin/env bash
# BC5 exp 0439 (tag pw439 mode 3; the top session's plan of 11-23 after F916): the whole box slot in one script.
#   1. prep439d.sh (the kit with mkpw439 and pw439 mode 3); the outputs must be the laptop's stand-in results:
#      unit bc5LleAgc.cpp 1b724fbe (b34a7a26 + mkpw439), backend direct.cpp 67daa9d6 (4d870ac7 + pw439patch with
#      mode 3), pw0439.hpp 3b482094; every other new/ and be/ file as 47e76e93's.
#   2. box439b2.sh into d2/priv9 (private; nothing shared written), the start-up rows checked on the first run.
#   3. ab439: ctl x3 against BC5_0439_PIECE_WAITS=3 x3, interleaved, fresh saves, shots every 15 s from 45 s (the
#      black-frame count), then ONE deliberate mode-2 run, last (pw2), whose timeout probe now dumps the pieces of the
#      hung buffers (the inner wait of F916). A GPU kernel line after any run stops the series (ab439's own rule).
# Run on the box, on the top session's word, as one named unit (it takes the lock through st439.sh per run):
#   systemd-run --user --unit=x439m3 --collect -p RuntimeMaxSec=5400 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439m3.sh > slot439m3.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2
stop() { echo "slot439m3 STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
cd "$K" || exit 1
date "+start %F %T"
bash prep439d.sh > m3-prep.txt 2>&1 || { tail -5 m3-prep.txt; stop prep; }
tail -3 m3-prep.txt | cut -c1-1200
NEW_PINS="ajm.cpp=44e01c8b atrac9_decoder.h=402d5d10 bc5LleAgc.cpp=1b724fbe controller.cpp=f0408c33 cw0439.hpp=9f1436d3 dc0439.hpp=c05cca6d dm0439.hpp=f2bf23e1 fp0439.hpp=9594ccf0 libAmpr.cpp=f5c78bef libVideoDec2.cpp=a315ac6d main.cpp=6b8e4411 pthread.cpp=f1ff5b6e sr0439b.hpp=2d2c56d3 switch_defaults.hpp=a3550fed tc0439.hpp=82404073 vf0439.hpp=6f589325 videoDec2Decoder.cpp=c63e3b5c videoOut.cpp=11f5e977 window.cpp=ee925d6c"
BE_PINS="src/direct.cpp=67daa9d6 src/full_state.cpp=c49ae21f src/policy.cpp=ea26c088 include/bc5/ib_chain.hpp=11df8b8f include/bc5/ds0439.hpp=c2b318af include/bc5/pw0439.hpp=3b482094"
BASE_PINS="patch d45618c6 normal 28ab1389 lean b0f856ed archive ed9f5dfe swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS"
(cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp" \
    EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv9" bash box439b2.sh > "$K/m3-build.txt" 2>&1) || { grep -a "STOP\|build rc" "$K/m3-build.txt" | tail -4; stop build; }
grep -a "build rc\|private normal\|shared after" "$K/m3-build.txt" | tail -4 | cut -c1-300
P=$(m8 "$D/priv9/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv9/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
echo "binary $P"
touch m3-mark
AB439_ARMS="ctl:$P m3:$P ctl2:$P m32:$P ctl3:$P m33:$P pw2:$P" AB439_SHOTS="45 60 75 90 105 120" AB439_BOUND=125 bash ab439.sh
L=$(find "$HOME/bc5-work/exp0439/runs" -maxdepth 1 -name "st439-*" -newer m3-mark | sort | head -1) # the slot's first run
[ -n "$L" ] && bash rowcheck439.sh "$L/play-last.log" "$D/new/switch_defaults.hpp"
date "+end %F %T"
