#!/usr/bin/env bash
# BC5 exp 0439 (tags ph439, dk439; the top session's orders of 11-23 after the mode-3 slot): the hold's slot in one script.
#   0. read only: the box's Mesa ac_surface.c lines on DCC independent 64B/128B blocks (whether Mesa gives shader-readable
#      DCC 128-byte independent blocks on GFX10 or only on GFX10_3), into ph-mesa-dcc.txt (the grid question, README).
#   1. prep439d.sh (mkb2439 with BC5_DIRECT_DCC_PRESENT=2 and BC5_DIRECT_EAGER_GPU_WRITE=1 as kSoft rows for every title, mksr439b with dk439's census
#      columns, mkpw439 with the chain-following piece dump, then mkph439, the dcb hold; mkdk439be, the dk439 arm, in the
#      backend); expected from the laptop stand-in chain (it reproduces b34a7a26 and a0afc355 with the old scripts):
#      unit bc5LleAgc.cpp cdcb13d5, sr0439b.hpp f294f3fd, new/pw0439.hpp 3b482094, backend direct.cpp 5706c7b3 (9dbecafe before the -Werror fix of 11-23 12:50),
#      be/include/bc5/pw0439.hpp 3b482094 and dk0439.hpp 565f3d80; switch_defaults.hpp cannot be pinned on the laptop
#      (the tree's header 7af89ba1 is on the box only): it must differ from the previous kit's a3550fed by exactly two
#      added lines, the EAGER_GPU_WRITE and DCC_PRESENT rows; the rest as 47e76e93's.
#      11-23 ~12:50: re-pinned on bakeR (the shared state since 12:31: tree diff 8a9ed0cf = 0001 d45618c6 + 0002 b54b7928,
#      normal 77d0d372, lean 506bd936, archive 5f16667a; backend policy.cpp 99303017 with the register catcher, so the
#      kit's policy.cpp is e8541e0a, the same edits; direct.cpp unchanged). The private build carries 0002's modules
#      (its objects and archive members are the shared ones).
#   2. box439b2.sh into d2/priv10 (private); the start-up rows checked on the slot's first run.
#   3. ab439: ctl x3 against ph (BC5_0439_PIECE_WAITS=3 with the hold, BC5_0439_PIECE_HOLD on) x3, interleaved, fresh
#      saves, shots every 15 s from 45 s (the black-frame count).
#   3b. the dk439 arm x2 (BC5_0439_DCC_UNCOMPRESSED=1: colour targets written without DCC, their keys set to uncompressed;
#      the grid is visible in this scene's shots: compare the same crops against the controls).
#   4. one scripted capture (ctl words, L3+R3 at ~95 s in the writing scene): sr439b's census with dk439's columns (the
#      ID targets' DCC_CONTROL, DCC_BASE and key histogram, the reads' V# words 6-7); the reader's output to ph-cap.txt.
#   5. ONE deliberate mode-2 run, last (pw2), whose timeout probe now follows the chains (the inner wait of F917).
#   A GPU kernel line stops the series (ab439's and this script's rule); the deliberate pw2 is the slot's last run.
# Run on the box, on the top session's word, as one named unit:
#   systemd-run --user --unit=x439ph --collect -p RuntimeMaxSec=5400 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439ph.sh > slot439ph.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2
stop() { echo "slot439ph STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; } # st439.sh's count, no sudo
cd "$K" || exit 1
date "+start %F %T"
{ grep -n "independent_128B\|independent_64B\|max_compressed_block_size\|GFX10_3" "$HOME/src/mesa/src/amd/common/ac_surface.c" 2> /dev/null | head -60 || echo "no ac_surface.c in ~/src/mesa"; } > ph-mesa-dcc.txt
{ [ "$(m8 "$D/new/switch_defaults.hpp")" = a3550fed ] && cp "$D/new/switch_defaults.hpp" ph-swd-before.hpp; } || [ "$(m8 ph-swd-before.hpp 2> /dev/null)" = a3550fed ] || stop "neither d2/new/switch_defaults.hpp nor a saved ph-swd-before.hpp is the previous kit's a3550fed" # a re-run: the first run's prep replaced d2/new
bash prep439d.sh > ph-prep.txt 2>&1 || { tail -5 ph-prep.txt; stop prep; }
dl=$(diff ph-swd-before.hpp "$D/new/switch_defaults.hpp" | grep -c '^[<>]'); da=$(diff ph-swd-before.hpp "$D/new/switch_defaults.hpp" | grep -c '^> .*{"BC5_DIRECT_\(DCC_PRESENT", "2"\|EAGER_GPU_WRITE", "1"\)}')
[ "$dl" = 2 ] && [ "$da" = 2 ] || stop "switch_defaults.hpp: $dl changed lines, $da of them the two new kSoft rows (want 2 and 2)"
SWD=$(m8 "$D/new/switch_defaults.hpp"); echo "switch_defaults.hpp $SWD: two added lines, the EAGER_GPU_WRITE and DCC_PRESENT kSoft rows"
tail -3 ph-prep.txt | cut -c1-1200
NEW_PINS="ajm.cpp=44e01c8b atrac9_decoder.h=402d5d10 bc5LleAgc.cpp=cdcb13d5 controller.cpp=f0408c33 cw0439.hpp=9f1436d3 dc0439.hpp=c05cca6d dm0439.hpp=f2bf23e1 fp0439.hpp=9594ccf0 libAmpr.cpp=f5c78bef libVideoDec2.cpp=a315ac6d main.cpp=6b8e4411 pw0439.hpp=3b482094 pthread.cpp=f1ff5b6e sr0439b.hpp=f294f3fd switch_defaults.hpp=$SWD tc0439.hpp=82404073 vf0439.hpp=6f589325 videoDec2Decoder.cpp=c63e3b5c videoOut.cpp=11f5e977 window.cpp=ee925d6c"
BE_PINS="src/direct.cpp=5706c7b3 src/full_state.cpp=c49ae21f src/policy.cpp=e8541e0a include/bc5/ib_chain.hpp=11df8b8f include/bc5/ds0439.hpp=c2b318af include/bc5/pw0439.hpp=3b482094 include/bc5/dk0439.hpp=565f3d80"
BASE_PINS="patch 8a9ed0cf normal 77d0d372 lean 506bd936 archive 5f16667a swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS BC5_0439_PIECE_HOLD BC5_0439_DCC_UNCOMPRESSED"
(cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp" \
    EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv10" bash box439b2.sh > "$K/ph-build.txt" 2>&1) || { grep -a "STOP\|build rc" "$K/ph-build.txt" | tail -4; stop build; }
grep -a "build rc\|private normal\|shared after" "$K/ph-build.txt" | tail -4 | cut -c1-300
P=$(m8 "$D/priv10/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv10/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
echo "binary $P"
touch ph-mark
gs=$(gl)
AB439_ARMS="ctl:$P ph:$P ctl2:$P ph2:$P ctl3:$P ph3:$P dk:$P dk2:$P" AB439_SHOTS="45 60 75 90 105 120" AB439_BOUND=125 bash ab439.sh
L=$(find "$HOME/bc5-work/exp0439/runs" -maxdepth 1 -name "st439-*" -newer ph-mark | sort | head -1) # the slot's first run
[ -n "$L" ] && bash rowcheck439.sh "$L/play-last.log" "$D/new/switch_defaults.hpp"
g0=$(gl)
[ "$g0" = "$gs" ] || stop "a GPU kernel line in the A/B ($gs -> $g0): no capture, no mode-2 run"
FD=$HOME/bc5-data/priv/frames
before=$(ls "$FD" 2> /dev/null | wc -l)
ST_CMD="wait 95000|hold l3|hold r3|wait 1500|release l3|release r3" ST_BOUND=200 ST_SHOTS="60 90 100 120 150 190" bash st439.sh "$P" 2>&1 | tail -1
[ "$(gl)" = "$g0" ] || stop "a GPU kernel line after the capture run"
C=$(ls -td "$FD"/sr439b-*-c0 2> /dev/null | head -1)
if [ "$(ls "$FD" | wc -l)" -gt "$before" ] && [ -n "$C" ]; then python3 -I sr439read.py "$C" > ph-cap.txt 2>&1; echo "capture $C: $(grep -c . ph-cap.txt) reader lines"; else echo "capture: none taken"; fi
AB439_ARMS="pw2:$P" AB439_SHOTS="45" AB439_BOUND=125 bash ab439.sh
date "+end %F %T"
