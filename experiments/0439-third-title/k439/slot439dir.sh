#!/usr/bin/env bash
# BC5 exp 0439 (tag dir439, the top session's order and advance GO of 11-23 ~18:50): which direction of the ordering race
# matters. Arms of BC5_0439_SERIAL (mksr439c.py; each bounded at 50 ms and journaled like mode 1):
#   ctl  none;
#   a    an acb submit waits until every earlier GFX job has completed;
#   b    a GFX submit waits until every earlier acb job has completed;
#   c    as a, only for an acb whose top-level stream waits (WAIT_REG_MEM) on a label a GFX job in flight has a pending
#        write of (the title asked for that order).
# Two runs each, interleaved (ctl a b c ctl a b c), fresh saves, no pad input, shots every 3 s from 45 s, the census arms
# as in slot439ser.sh (picture labels, ops.tsv, submits.tsv). Derived from slot439ser.sh (ctl vs mode 1), whose header
# follows.
# BC5 exp 0439 (tag ser439, the top session's order of 11-23 ~17:50): ctl vs BC5_0439_SERIAL=1 (each submit waits for every
# earlier job, 50 ms bound), three runs each, interleaved, with the census arms (picture labels, cblog, ops.tsv and
# submits.tsv for the last writers of the lit pass's inputs). Derived from slot439cb.sh: the CB-register log's slot (every draw's colour and
# depth target registers in pieces 140-175 of each armed frame, with each frame's picture as its label; ten arms a run,
# every 10 s from 50 s; DCC copies kept small, no raw dumps). Derived from slot439v3.sh: (each DCC colour
# target copied whole with its keys at every pass end of an armed frame, the COPY decompressed after the frame; the title's
# frame untouched). Derived from slot439rsv.sh (its header below describes that slot; the runs here are at the end).
#   1. prep439d.sh (the kit of slot439sc plus rsv439 in mksr439c), pinned below from the laptop stand-in chain;
#      box439b2.sh into d2/priv12 (private).
#   2. four scripted runs, interleaved, fresh saves, no pad input, 150 s, shots every 3 s from 45 s (the labels:
#      black / striped / good per shot, by eye): ctl, rsv (BC5_0439_DCC_RESOLVE=1), ctl, rsv.
#   3. two runs rsv + the pass census (BC5_0439_PASS_DUMP, arms at 60, 90, 120 s): with every DCC target decompressed
#      at its pass end before the census copies it, the copies of the lit colour and the G-buffer are plain pixels.
#   A GPU kernel line after any run stops the series.
# Run on the box, on the top session's word, as one named unit:
#   systemd-run --user --unit=x439dir --collect -p RuntimeMaxSec=3600 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439dir.sh > slot439dir.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2
stop() { echo "slot439dir STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; } # st439.sh's count, no sudo
cd "$K" || exit 1
date "+start %F %T"
# the top session's condition (11-23 ~17:15): no build beside another run either: wait once a minute for an empty lock and
# no emulator before the build too
for i in $(seq 1 40); do [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null || break; [ $i = 1 ] && echo "waiting before the build ($(date +%T)): lock [$(cat "$HOME/bc5-work/BOX-LOCK" 2> /dev/null)]"; sleep 60; done
{ [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null; } && stop "the box is still busy after 40 min"
echo "box free for the build ($(date +%T))"
bash prep439d.sh > dir-prep.txt 2>&1 || { tail -5 dir-prep.txt; stop prep; }
NEW_PINS="ajm.cpp=44e01c8b atrac9_decoder.h=402d5d10 bc5LleAgc.cpp=66c8ad10 controller.cpp=f0408c33 cw0439.hpp=9f1436d3 dc0439.hpp=c05cca6d dm0439.hpp=f2bf23e1 fp0439.hpp=9594ccf0 libAmpr.cpp=f5c78bef libVideoDec2.cpp=a315ac6d main.cpp=6b8e4411 pw0439.hpp=3b482094 pthread.cpp=f1ff5b6e sr0439b.hpp=f294f3fd sr0439c.hpp=bae0ebee switch_defaults.hpp=24f28ef3 tc0439.hpp=82404073 vf0439.hpp=6f589325 videoDec2Decoder.cpp=c63e3b5c videoOut.cpp=11f5e977 window.cpp=ee925d6c"
BE_PINS="src/direct.cpp=4c5ed838 src/full_state.cpp=c49ae21f src/policy.cpp=e8541e0a include/bc5/ib_chain.hpp=11df8b8f include/bc5/ds0439.hpp=c2b318af include/bc5/pw0439.hpp=3b482094 include/bc5/dk0439.hpp=565f3d80 include/bc5/sr0439c.hpp=bae0ebee"
BASE_PINS="patch 8a9ed0cf normal fd8e44e1 lean 1e47486a archive ba25f31c swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS BC5_0439_PIECE_HOLD BC5_0439_DCC_UNCOMPRESSED BC5_0439_PASS_DUMP BC5_0439_PASS_AT BC5_0439_PASS_MB BC5_0439_PASS_WINDOW BC5_0439_PASS_STRIDE BC5_0439_PASS_MEC BC5_0439_DCC_RESOLVE BC5_0439_PASS_DCC_ONLY BC5_0439_PASS_CBLOG BC5_0439_PASS_CBLOG_PIECES BC5_0439_PASS_NORAW BC5_0439_SERIAL"
(cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp" \
    EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv16" bash box439b2.sh > "$K/dir-build.txt" 2>&1) || { grep -a "STOP\|build rc\|error:" "$K/dir-build.txt" | tail -6; stop build; }
grep -a "build rc\|private normal\|shared after" "$K/dir-build.txt" | tail -4 | cut -c1-300
P=$(m8 "$D/priv16/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv16/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
echo "binary $P"
SHOTS=$(seq 45 3 147 | tr '\n' ' ')
PD=$HOME/bc5-data/priv/passes; mkdir -p "$PD" && chmod 700 "$PD"
: > dir-shots.txt
run() { # $1 name, $2 words
    local g0 out SH L
    g0=$(gl)
    out=$(ST_MORE="$2" ST_SHOTS="$SHOTS" ST_BOUND=165 bash st439.sh "$P" 2>&1 | tail -1)
    echo "$1 [$2]: $out"
    SH=$(echo "$out" | sed -n 's/.*shots in \(.*\)$/\1/p')
    [ -n "$SH" ] && echo "$1 $SH" >> dir-shots.txt
    L=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1)
    grep -a "tag ser439\|tag sr439c v3\|tag sr439c cblog" "$L/play-last.log" 2> /dev/null | tail -4 | cut -c1-300
    [ "$(gl)" = "$g0" ] || stop "a GPU kernel line in $1 ($g0 -> $(gl)): no further run"
    sleep 5
}
# the top session's condition (11-23 15:40): no emulator run while the reimpl session's CPU-only dry build runs
for i in $(seq 1 40); do pgrep -f 'bakeS/dry' > /dev/null || break; [ $i = 1 ] && echo "waiting for bakeS/dry to end ($(date +%T))"; sleep 60; done
pgrep -f 'bakeS/dry' > /dev/null && stop "bakeS/dry still running after 40 min"
# the top session's condition (11-23 ~16:25): wait (once a minute, up to 60 min) until BOX-LOCK is empty and no emulator
# runs; gate439.sh (in st439.sh) then refuses if this boot has a GPU fault line
g_start=$(gl)
for i in $(seq 1 60); do [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null || break; [ $i = 1 ] && echo "waiting for the box ($(date +%T)): lock [$(cat "$HOME/bc5-work/BOX-LOCK" 2> /dev/null)]"; sleep 60; done
{ [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null; } && stop "the box is still busy after 60 min"
[ "$(gl)" = "$g_start" ] || stop "a GPU kernel line appeared while waiting ($g_start -> $(gl)): no run"
bash gate439.sh > /dev/null 2>&1 || stop "gate439 refuses (a GPU fault line in this boot)"
echo "no bakeS/dry process ($(date +%T)): runs start"
run ctl1 "BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
L=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1); bash rowcheck439.sh "$L/play-last.log" "$D/new/switch_defaults.hpp"
run a1 "BC5_0439_SERIAL=a BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run b1 "BC5_0439_SERIAL=b BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run c1 "BC5_0439_SERIAL=c BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run ctl2 "BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run a2 "BC5_0439_SERIAL=a BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run b2 "BC5_0439_SERIAL=b BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
run c2 "BC5_0439_SERIAL=c BC5_0439_PASS_DUMP=$PD BC5_0439_PASS_DCC_ONLY=1 BC5_0439_PASS_MB=64 BC5_0439_PASS_NORAW=1 BC5_0439_PASS_CBLOG=1 BC5_0439_PASS_AT=50,70,90,110,130"
du -sh "$PD"
date "+end %F %T"
