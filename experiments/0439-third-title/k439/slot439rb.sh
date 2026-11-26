#!/usr/bin/env bash
# BC5 exp 0439 (tag rr439b, build b, the top session's order of 11-23 ~20:10): the naming run of mode 2. One build (unit
# with mksr439c.py's rr439b tail: the job table and the whole piece walk inside the timeout probe, the fault record held
# while probes run, each unmet piece wait's pending writers, LOAD_SH_REG_INDEX tables, each dispatch's user data); then ONE
# run, chosen by the argument (the top session reboots between the two):
#   slot439rb.sh m2   BC5_0439_PIECE_WAITS=2 with the record (no ring rule)
#   slot439rb.sh rf   BC5_0439_PIECE_WAITS=2 BC5_0439_RING_FREE=1 (the record is on with it)
#   slot439rb.sh w2   as b2 plus BC5_0439_RR_WATCH=0x2000008200,8,0x20 (tag rr439d, 11-23 ~20:50: the eight per-frame counters
#                     at every submit and the timeout; the last 64 jobs with their pieces searched for them). Build d.
#   slot439rb.sh fa   arm A (tag f4p439, 11-23 ~21:00): mode 2 + RING_BIND=2 + BC5_0439_F4_PIECES=1 (F2 counts the writer's kept
#                     piece waits, so F4 adds no dependency in that cycle) + the watch. Build e.
#   slot439rb.sh tc   arm C (tag tsp439|tag va439|ho430 F2, 11-23 ~21:05): mode 2 + RING_BIND=2 + BC5_0439_DCB_TAIL_SPLIT=1 (the dcb root before its
#                     tail chain is its own job, so F4 orders behind the release it waits for) + the watch. Build f, with A.
#   slot439rb.sh fn   arm A + the kernel-submit record (tag fn439, 11-23 ~21:25: BC5_0439_FN_RECORD=1, mkfn439be.py; each
#                     submit's libdrm ring, deps, fence and IB addresses; at a timeout the fences' status). Build g.
#   slot439rb.sh k0   arm A + record + BC5_GUARD_K1R=0 (11-23 ~21:45: fn2 named every GPU unmap as K1R's zero-cover drop; an
#                     unmap's page-table clear waits for every in-flight job of the VM, so no cover = no unmap). Build h.
#   slot439rb.sh vd   arm A + record + BC5_0439_VA_DEFER=1 (tag va439, mkvd439be.py: no GPU unmap while a GFX job is in flight;
#                     kept and issued when no GFX job runs or a new mapping overlaps). Build i.
#   slot439rb.sh vk   vd + BC5_GUARD_K1R=0 (the top session, 11-23 ~21:52: with the cover on, a cover drop is an unmap that a map
#                     overlaps, issued at once; no cover isolates the deferral of the guest unmaps). Build j: + f4p439 step 2, tag va439.
#   slot439rb.sh vf   vk + BC5_0439_F4_OFF=1 (tag f4off439, 11-23 ~22:25: no ho430 F4 dependency; F848's risk taken). Build l.
#   slot439rb.sh vn   vf + BC5_0439_NO_MERGE=1 (tag nm439, 11-23 ~23:00: no direct-memory BO merge, so no re-cut). Build m.
#   slot439rb.sh vs   vn + BC5_DIRECT_SLOT_PREALLOC=1024:1024 (11-23 ~23:05: vn hung on a 256 KiB job slot regrown for a
#                     65,608-dword acb: an unmap of the slot while the GFX job ran). Build m, no new build.
#   slot439rb.sh v3   vs with BC5_0439_RING_BIND=3 (11-23 ~23:20: not behind another queue's waiter). Build n.
#   slot439rb.sh ctl  the control (the shortcut's PIECE_WAITS=1, the record on)
#   slot439rb.sh b2   BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 (tag rb439, ring binding v2; 11-23 ~20:30, after m2 named
#                     the head-of-line cycle on ring 0; the record is on with it). Build c (unit 3299bdfd, priv30).
# The build is skipped when the pinned binary of this kit is already there (the second call). Shots every 3 s.
# Derived from slot439dir.sh, whose header follows.
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
#   systemd-run --user --unit=x439rb --collect -p RuntimeMaxSec=3600 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439rb.sh m2 > slot439rb-m2.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2
stop() { echo "slot439rb STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; } # st439.sh's count, no sudo
ARM=${1:-}; case "$ARM" in m2|rf|b2|ctl|w2|fa|tc|fn|k0|vd|vk|vf|vn|vs|v3) ;; *) echo "slot439rb: argument m2, rf, b2, w2, fa, tc, fn, k0, vd, vk, vf, vn, vs, v3 or ctl"; exit 2 ;; esac
cd "$K" || exit 1
date "+start %F %T"
# the top session's condition (11-23 ~17:15): no build beside another run either: wait once a minute for an empty lock and
# no emulator before the build too
for i in $(seq 1 40); do [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null || break; [ $i = 1 ] && echo "waiting before the build ($(date +%T)): lock [$(cat "$HOME/bc5-work/BOX-LOCK" 2> /dev/null)]"; sleep 60; done
{ [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null; } && stop "the box is still busy after 40 min"
echo "box free for the build ($(date +%T))"
if [ -s "$D/priv30/normal/kyty_emulator" ] && [ -f "$K/rn-build.txt" ] && grep -q "build rc 0" "$K/rn-build.txt"; then echo "build b already made: $(grep -a "private normal" "$K/rn-build.txt" | tail -1)"; else
bash prep439d.sh > rn-prep.txt 2>&1 || { tail -5 rn-prep.txt; stop prep; }
NEW_PINS="ajm.cpp=44e01c8b atrac9_decoder.h=402d5d10 bc5LleAgc.cpp=f9a46216 f4p0439.hpp=a3c8251d controller.cpp=f0408c33 cw0439.hpp=9f1436d3 dc0439.hpp=c05cca6d dm0439.hpp=f2bf23e1 fp0439.hpp=9594ccf0 libAmpr.cpp=f5c78bef libVideoDec2.cpp=a315ac6d main.cpp=6b8e4411 pw0439.hpp=3b482094 pthread.cpp=f1ff5b6e sr0439b.hpp=f294f3fd sr0439c.hpp=bae0ebee switch_defaults.hpp=24f28ef3 tc0439.hpp=82404073 vf0439.hpp=6f589325 videoDec2Decoder.cpp=c63e3b5c videoOut.cpp=11f5e977 window.cpp=ee925d6c"
BE_PINS="src/direct.cpp=1ae115f4 src/full_state.cpp=c49ae21f src/policy.cpp=e8541e0a include/bc5/ib_chain.hpp=11df8b8f include/bc5/ds0439.hpp=c2b318af include/bc5/pw0439.hpp=3b482094 include/bc5/dk0439.hpp=565f3d80 include/bc5/sr0439c.hpp=bae0ebee"
BASE_PINS="patch 8a9ed0cf normal fd8e44e1 lean 1e47486a archive ba25f31c swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS BC5_0439_PIECE_HOLD BC5_0439_DCC_UNCOMPRESSED BC5_0439_PASS_DUMP BC5_0439_PASS_AT BC5_0439_PASS_MB BC5_0439_PASS_WINDOW BC5_0439_PASS_STRIDE BC5_0439_PASS_MEC BC5_0439_DCC_RESOLVE BC5_0439_PASS_DCC_ONLY BC5_0439_PASS_CBLOG BC5_0439_PASS_CBLOG_PIECES BC5_0439_PASS_NORAW BC5_0439_SERIAL BC5_0439_RR_RECORD BC5_0439_RING_FREE BC5_0439_RING_BIND BC5_0439_RR_WATCH BC5_0439_F4_PIECES BC5_0439_DCB_TAIL_SPLIT BC5_0439_FN_RECORD BC5_0439_VA_DEFER BC5_0439_F4_OFF BC5_0439_NO_MERGE"
(cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp" \
    EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv30" bash box439b2.sh > "$K/rn-build.txt" 2>&1) || { grep -a "STOP\|build rc\|error:" "$K/rn-build.txt" | tail -6; stop build; }
grep -a "build rc\|private normal\|shared after" "$K/rn-build.txt" | tail -4 | cut -c1-300
fi
P=$(m8 "$D/priv30/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv30/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
echo "binary $P"
SHOTS=$(seq 45 3 147 | tr '\n' ' ')
PD=$HOME/bc5-data/priv/passes; mkdir -p "$PD" && chmod 700 "$PD"
: > rb-shots.txt
run() { # $1 name, $2 words
    local g0 out SH L
    g0=$(gl)
    out=$(ST_MORE="$2" ST_SHOTS="$SHOTS" ST_BOUND=165 bash st439.sh "$P" 2>&1 | tail -1)
    echo "$1 [$2]: $out"
    SH=$(echo "$out" | sed -n 's/.*shots in \(.*\)$/\1/p')
    [ -n "$SH" ] && echo "$1 $SH" >> rb-shots.txt
    L=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1)
    grep -a "tag ser439\|tag rr439\|tag rb439\|tag f4p439\|f4p439:\|tag tsp439\|tag va439\|ho430 F2\|ho430 F4" "$L/play-last.log" 2> /dev/null | tail -4 | cut -c1-300
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
L0=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1)
case "$ARM" in
    m2) run m2 "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2" ;;
    rf) run rf "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_FREE=1" ;;
    b2) run b2 "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2" ;;
    ctl) run ctl "BC5_0439_RR_RECORD=1" ;;
    v3) run v3 "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=3 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1 BC5_GUARD_K1R=0 BC5_0439_F4_OFF=1 BC5_0439_NO_MERGE=1 BC5_DIRECT_SLOT_PREALLOC=1024:1024" ;;
    vs) run vs "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1 BC5_GUARD_K1R=0 BC5_0439_F4_OFF=1 BC5_0439_NO_MERGE=1 BC5_DIRECT_SLOT_PREALLOC=1024:1024" ;;
    vn) run vn "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1 BC5_GUARD_K1R=0 BC5_0439_F4_OFF=1 BC5_0439_NO_MERGE=1" ;;
    vf) run vf "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1 BC5_GUARD_K1R=0 BC5_0439_F4_OFF=1" ;;
    vk) run vk "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1 BC5_GUARD_K1R=0" ;;
    vd) run vd "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_0439_VA_DEFER=1" ;;
    k0) run k0 "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1 BC5_GUARD_K1R=0" ;;
    fn) run fn "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20 BC5_0439_FN_RECORD=1" ;;
    tc) run tc "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_DCB_TAIL_SPLIT=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20" ;;
    fa) run fa "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_F4_PIECES=1 BC5_0439_RR_WATCH=0x2000008200,8,0x20" ;;
    w2) run w2 "BC5_0439_RR_RECORD=1 BC5_0439_PIECE_WAITS=2 BC5_0439_RING_BIND=2 BC5_0439_RR_WATCH=0x2000008200,8,0x20" ;;
esac
L=$(ls -td "$HOME/bc5-work/exp0439/runs"/st439-* | head -1); [ "$L" != "$L0" ] && bash rowcheck439.sh "$L/play-last.log" "$D/new/switch_defaults.hpp"
date "+end %F %T"
