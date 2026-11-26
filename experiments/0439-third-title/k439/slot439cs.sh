#!/usr/bin/env bash
# BC5 exp 0439 (tag cs439, the top session's order of 11-24 ~14:30, its slot after exp 0442): the edge-block suspects.
#   0. the 14 GB cleanup agreed at 13:33 (d2/priv11..priv29, the obsolete pinned binaries; keeps: 3939f323 (the shortcut),
#      e96631ec (arm b), 757bd9e9 (undo), every binary a k439 launcher still names);
#   1. the build: prep439d.sh (the kit of priv30, e96631ec) + mkcs439be.py (cs0439.hpp: BC5_0439_CS_COUNT, PUSH_NO_CLEAR,
#      PIECE_STATE_STACK, PASS_CONTEXT_CONTROL, REGTAB_DUMP; all off by default) into d2/priv31 with state_stack.cpp as a
#      fourth backend unit;
#   2. the arms, each mw439.sh from a fresh copy of the 10:46 snapshot, the edge route (stick moves, a shot every 2 s from
#      125 s), MS_KLOG=1, EAGER_GPU_WRITE off in all, bound CS_BOUND (default 420 s):
#        cE1  3939f323, DCC_PRESENT=1 (suspect 3: no dc439 flip job)
#        cE2  3939f323, DCC_PRESENT=2 (as the shortcut)
#        N0   the new build, all cs439 switches off, + CS_COUNT=1 (counts only) + the register tables of 2 frames at 200 and
#             260 s (REGTAB_DUMP, private) - the new build's own baseline (it is priv30's kit, not 3939f323's)
#        N1   N0's words + PUSH_NO_CLEAR=1 + PIECE_STATE_STACK=1 (suspect 1)
#        N2   N0's words + PASS_CONTEXT_CONTROL=1 alone (suspect 2; last: it can hang the GPU)
#        N3   N0 + COND_POP_NOP=1 (11-24 15:05, from N0's counts: the pop under COND_EXEC) + the tables at 150/200 s
#        D0   N0 with the tables at 150/200 s (the first build's dump keyed on the root alone and never fired)
#        G1   priv33: CC_GUARDED + COND_POP_NOP + MLOCK_IMPORTS (the next candidate), counts and the lock limit noted
#        P0/P1  priv33 with CC_GUARDED + COND_POP_NOP, MLOCK_IMPORTS off/on, memp439.py pressure from outside (CS_PRESS,
#             default 180 s in, MemAvailable 1500 MiB, held 90 s; brake at memory PSI full 10 % or 700 MiB)
#      CS_PRIV picks d2/priv<N> (31 first; 32 with COND_POP_NOP and the dump fix). A new GPU kernel line ends the series (R55). CS_ARMS picks arms (default "cE1 cE2 N0 N1 N2").
# Run on the box, on the top session's word, as one named unit:
#   systemd-run --user --unit=x439cs --collect -p RuntimeMaxSec=7200 --working-directory=$HOME/bc5-work/exp0439/k439 \
#       bash -c 'ulimit -c 0; bash slot439cs.sh > raw/slot439cs.txt 2>&1'
set -u
K=$HOME/bc5-work/exp0439/k439; D=$HOME/bc5-work/exp0439/d2; E=$HOME/bc5-work/exp0439
stop() { echo "slot439cs STOP: $*"; date +%T; exit 1; }
m8() { md5sum < "$1" | cut -c1-8; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
cd "$K" || exit 1
date "+start %F %T"
{ [ -s "$HOME/bc5-work/BOX-LOCK" ] || pgrep "^kyty_emulator" > /dev/null; } && stop "the box is busy: lock [$(cat "$HOME/bc5-work/BOX-LOCK" 2> /dev/null)]"
g_start=$(gl)

# 0. cleanup (no saves, no shared builds; only exp 0439's own obsolete build trees and pinned binaries)
if [ "${CS_CLEAN:-1}" = 1 ]; then
    before=$(df -B1M --output=avail "$HOME" | tail -1)
    for n in $(seq 11 29); do [ -d "$D/priv$n" ] && rm -rf "$D/priv$n"; done
    keep=" 3939f323 e96631ec 757bd9e9 $(grep -ohE 'kyty_emulator\.[0-9a-f]{8}' "$K"/*.sh "$K"/t3-test.sh* 2> /dev/null | cut -d. -f2 | sort -u | tr '\n' ' ') "
    for f in "$K"/normal/kyty_emulator.????????; do
        h=${f##*.}; case "$keep" in *" $h "*) continue ;; esac
        rm -f "$f"
    done
    after=$(df -B1M --output=avail "$HOME" | tail -1)
    echo "cleanup: kept binaries [$keep]; freed $(( (after - before) / 1024 )) GiB ($before -> $after MiB available)"
fi

# 1. the build
if [ -s "$D/priv${CS_PRIV:-31}/normal/kyty_emulator" ] && grep -q "build rc 0" "$K/cs-build${CS_PRIV:-31}.txt" 2> /dev/null; then
    echo "build already made: $(grep -a "private normal" "$K/cs-build${CS_PRIV:-31}.txt" | tail -1)"
else
    bash prep439d.sh > cs-prep.txt 2>&1 || { tail -5 cs-prep.txt; stop prep; }
    cp "$HOME/bc5-work/d19/export/backend/src/state_stack.cpp" "$D/be/src/" && cp "$K/cs0439.hpp" "$D/be/include/bc5/" || stop "copy state_stack.cpp / cs0439.hpp"
    python3 -I "$K/mkcs439be.py" "$D/be" || stop mkcs439be
    if [ "${CS_VZ:-0}" = 1 ]; then python3 -I "$K/mkvz439.py" "$D/new" || stop mkvz439; fi
    if [ "${CS_VLON:-0}" = 1 ]; then python3 -I "$K/mkvlon439.py" "$D/new" || stop mkvlon439; fi
    if [ "${CS_MG:-0}" = 1 ]; then python3 -I "$K/mkmg439.py" "$D/new" "$D/new" || stop mkmg439; fi
    if [ "${CS_GV:-0}" = 1 ]; then python3 -I "$K/mkgv439.py" "$D/new" || stop mkgv439; fi
    if [ "${CS_VT:-0}" = 1 ]; then python3 -I "$K/mkvt439.py" "$D/new" || stop mkvt439; fi
    if [ "${CS_FL:-0}" = 1 ]; then python3 -I "$K/mkfl439.py" "$D/new" || stop mkfl439; fi # 11-25 (tag fl439): the flip-label catcher and BC5_0439_FLIP_WAIT_PENDING # 11-25 (tag vt439): the rainbow trigger, BC5_0439_RB_TRIGGER=<n> # 11-25 (tag gv439): GPU-mapped against CPU-only census, BC5_0439_GV_CENSUS=1 # 11-24 night (tag mg439): the growth census, BC5_0439_MG_CENSUS=1 # 11-24 night (tag vlon439): vl439 (b) on unless "0" # 11-24 night (tag vz439): the slot dump and watch, BC5_0439_VD2_DUMP
    NEW_PINS=$(cd "$D/new" && for f in *; do echo -n "$f=$(m8 "$f") "; done)
    BE_PINS=$(cd "$D/be" && for f in src/direct.cpp src/full_state.cpp src/policy.cpp src/state_stack.cpp include/bc5/ib_chain.hpp include/bc5/ds0439.hpp include/bc5/pw0439.hpp include/bc5/dk0439.hpp include/bc5/sr0439c.hpp include/bc5/cs0439.hpp; do echo -n "$f=$(m8 "$f") "; done)
    echo "kit new: $NEW_PINS"; echo "kit be: $BE_PINS"
    BASE_PINS="patch 8a9ed0cf normal fd8e44e1 lean 1e47486a archive ba25f31c swd 7af89ba1 unit ea564dbd vout 6785425e ajm 971b3d66 a9 c2f248cb"
    [ -n "${CS_BASE_PINS:-}" ] && BASE_PINS=$CS_BASE_PINS # 11-24 night (vz439): the host-native shared builds of 17:15-17:23 (same source pins)
    EXTRA_GAINED="KYTY_BC5_APR_RESULT_ORDER KYTY_BC5_VD2_SIZES BC5_0439_BLACK_CATCH BC5_0439_SOFT_LINES BC5_0439_SOFT_WAIT_MS BC5_0439_FLIP_LABEL_GPU BC5_0439_FLIP_LABEL_PIECES BC5_0439_CHAIN_WRITERS BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_GC_TF_RING BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_0439_PAD_TOUCH KYTY_BC5_0439_PAD_TIME BC5_0439_FRAME_DUMP KYTY_BC5_VD2_FILL BC5_0439_PIECE_WAITS BC5_0439_PIECE_HOLD BC5_0439_DCC_UNCOMPRESSED BC5_0439_PASS_DUMP BC5_0439_PASS_AT BC5_0439_PASS_MB BC5_0439_PASS_WINDOW BC5_0439_PASS_STRIDE BC5_0439_PASS_MEC BC5_0439_DCC_RESOLVE BC5_0439_PASS_DCC_ONLY BC5_0439_PASS_CBLOG BC5_0439_PASS_CBLOG_PIECES BC5_0439_PASS_NORAW BC5_0439_SERIAL BC5_0439_RR_RECORD BC5_0439_RING_FREE BC5_0439_RING_BIND BC5_0439_RR_WATCH BC5_0439_F4_PIECES BC5_0439_DCB_TAIL_SPLIT BC5_0439_FN_RECORD BC5_0439_VA_DEFER BC5_0439_F4_OFF BC5_0439_NO_MERGE BC5_0439_CS_COUNT BC5_0439_PUSH_NO_CLEAR BC5_0439_PIECE_STATE_STACK BC5_0439_PASS_CONTEXT_CONTROL BC5_0439_REGTAB_DUMP BC5_0439_REGTAB_AT BC5_0439_REGTAB_MIN_DW BC5_0439_COND_POP_NOP BC5_0439_CC_CENSUS BC5_0439_CC_GUARDED BC5_0439_MLOCK_IMPORTS BC5_0439_VD2_DUMP BC5_0439_VD2_DUMP_DIR BC5_0439_MG_CENSUS BC5_0439_GV_CENSUS BC5_0439_RB_TRIGGER BC5_0439_RB_ARM BC5_0439_RB_FROM BC5_0439_FL_CATCH BC5_0439_FLIP_WAIT_PENDING BC5_0439_FLIP_WAIT_MS"
    (cd "$D" && BASE_PINS="$BASE_PINS" NEW_PINS="$NEW_PINS" BE_PINS="$BE_PINS" UNITS_BE="src/direct.cpp src/full_state.cpp src/policy.cpp src/state_stack.cpp" \
        EXTRA_KY="src/libs/libVideoDec2.cpp src/libs/controller.cpp src/libs/videoDec2Decoder.cpp${CS_MG:+ src/kernel/memory.cpp}" \
        B2_HOST="${CS_HOST:-0}" EXTRA_GAINED="$EXTRA_GAINED" E_DIR="$D/priv${CS_PRIV:-31}" bash box439b2.sh > "$K/cs-build${CS_PRIV:-31}.txt" 2>&1) || { grep -a "STOP\|build rc\|error:" "$K/cs-build${CS_PRIV:-31}.txt" | tail -8; stop build; }
    grep -a "build rc\|private normal\|shared after\|private archive" "$K/cs-build${CS_PRIV:-31}.txt" | tail -4 | cut -c1-300
fi
P=$(m8 "$D/priv${CS_PRIV:-31}/normal/kyty_emulator")
[ -f "normal/kyty_emulator.$P" ] || { cp -p "$D/priv${CS_PRIV:-31}/normal/kyty_emulator" "normal/kyty_emulator.$P" && chmod a-w "normal/kyty_emulator.$P"; } || stop "pin $P"
strings -n 6 "normal/kyty_emulator.$P" | grep -c "tag cs439" | sed "s/^/binary $P: cs439 strings /"
[ "$(gl)" = "$g_start" ] || stop "a GPU kernel line during the build ($g_start -> $(gl))"

# 2. the arms
B=${CS_BOUND:-420}; SRC=$HOME/bc5-data/saves/TITLE3-20261124-x439mwu-end
RT="wait40 cross wait50 cross wait60 cross wait70 cross wait80 cross wait95 cross wait110 cross wait125 edge"
TD=$HOME/bc5-data/priv/regtab; mkdir -p "$TD" && chmod 700 "$TD"
arm() { # $1 tag, $2 mw439 arm (a = 3939f323, b = MW_PIN_B), $3 words dropped (regex), $4 words added
    local g0; g0=$(gl)
    echo "== $(date +%T) arm $1 [drop: $3] [add: $4]"
    # 11-24 (tag mp439): with ARM_PRESS="<delay s> <target MemAvailable MiB> <hold s>", memp439.py applies memory pressure
    # from outside that many seconds after the start; 40 s after the start the emulator's lock limit and VmLck are noted
    ( sleep 40; p=$(pgrep -o "^kyty_emulator") && echo "limits: $(grep -i 'locked memory' /proc/$p/limits | tr -s ' ') $(grep -E 'VmLck|VmPin' /proc/$p/status | tr -s ' \t' ' ' | tr '\n' ' ')" ) &
    # 11-24 night (tag vz439): with ARM_FDS=1 the emulator's open files (path, size) are noted for 100 s, a line the first time each is seen
    if [ "${ARM_FDS:-0}" = 1 ]; then ( t0=$(date +%s); declare -A seen; while [ $(( $(date +%s) - t0 )) -lt 100 ]; do p=$(pgrep -o "^kyty_emulator") && for f in /proc/$p/fd/*; do l=$(readlink "$f" 2> /dev/null) || continue; case $l in /*) ;; *) continue ;; esac; [ -n "${seen[$l]:-}" ] && continue; seen[$l]=1; echo "$(( $(date +%s) - t0 )) s $(stat -Lc %s "$f" 2> /dev/null) $l"; done; sleep 0.5; done ) > "$K/raw/fd-$1.txt" 2>&1 & fi
    # 11-24 night (vz439f): ARM_STALL="<s after the emulator appears> <stop s>": the emulator is stopped (SIGSTOP) that long, then continued
    if [ -n "${ARM_STALL:-}" ]; then ( read -r sa sl <<< "$ARM_STALL"; t=0; until pgrep -o "^kyty_emulator" > /dev/null || [ $t -gt 600 ]; do sleep 0.1; t=$((t + 1)); done; sleep "$sa"; p=$(pgrep -o "^kyty_emulator") && { echo "stall: $(date +%T.%N | cut -c1-12) SIGSTOP $p"; kill -STOP "$p"; sleep "$sl"; kill -CONT "$p"; echo "stall: $(date +%T.%N | cut -c1-12) SIGCONT"; } ) > "$K/raw/stall-$1.txt" 2>&1 & fi
    [ "${ARM_IO:-0}" = 1 ] && { bash "$K/io439.sh" "$K/raw/io-$1.txt" > /dev/null 2>&1 & } # 11-25 (tag io439)
    [ "${ARM_SNAP:-0}" = 1 ] && { bash "$K/snap439.sh" "$K/raw/snap-$1" > /dev/null 2>&1 & } # 11-25 (tag sn439): the memory budget snapshots
    if [ -n "${ARM_PRESS:-}" ]; then ( read -r pd pt ph <<< "$ARM_PRESS"; sleep "$pd"; pgrep -o "^kyty_emulator" > /dev/null && python3 -I "$K/memp439.py" "$pt" "$ph" > "$K/raw/memp-$1.txt" 2>&1 ) & fi
    MW_LOGS="${ARM_LOGS:-1}" MW_CAPTURE="${ARM_CAPTURE:-1}" MW_GUARD_MB="${ARM_GUARD_MB:-}" MW_GUARD_IO="${ARM_GUARD_IO:-}" MW_CMD="${ARM_CMD:-}" MW_DISTROBOX=${ARM_DB:-0} MW_SDRUN_P="${ARM_SDP:-}" MS_KLOG=1 MS_INTERVAL=0.5 MW_TAGX=cs$1 MW_DROP="$3" MW_ADD="$4" MW_SAVE_SRC="${ARM_SRC-$SRC}" MW_SHOT_S=${ARM_SHOT_S:-100000} MW_SHOT_FROM=${ARM_SHOT_FROM:-30} MW_ROUTE=${ARM_ROUTE:-1} MW_RT="${ARM_RT:-$RT}" MW_WANT="${ARM_WANT:-performance}" MW_PIN_B=${ARM_PIN:-$P} MW_LEAN=${ARM_LEAN:-0} MW_MH_DIR="${ARM_MH:-}" \
        MW_UNTIL="$(date -d "+$((B / 60 + 2)) min" +%H:%M)" bash "$K/mw439.sh" "$2" "$B" 2>&1 | tail -3
    local L; L=$(ls -td "$E/runs"/mw439*-cs$1 2> /dev/null | head -1)
    grep -ah "tag cs439" "$L/play-last.log" 2> /dev/null | tail -3 | cut -c1-400
    [ "$(gl)" = "$g0" ] || stop "a GPU kernel line in arm $1 ($g0 -> $(gl)): no further arm"
    sleep 15
}
NB=${CS_NB:-"BC5_DIRECT_EAGER_GPU_WRITE|BC5_0439_NO_MERGE|BC5_0439_VA_DEFER"} # CS_NB: 11-24 (fn439) also BC5_GUARD_LEDGER for the live word list
for a in ${CS_ARMS:-cE1 cE2 N0 N1 N2}; do
    if [ -n "${CS_DEADLINE:-}" ]; then [ "$(date +%s)" -lt "$CS_DEADLINE" ] || { echo "slot439cs: past the deadline $(date -d @$CS_DEADLINE +%T): arm $a and later not run"; break; }; else # 11-24 night: an epoch deadline across midnight
    [ "$(date +%H%M)" -lt "${CS_LAST_START:-1633}" ] || { echo "slot439cs: past ${CS_LAST_START:-1633}: arm $a and later not run"; break; } fi
    case $a in
        cE1) arm cE1 a "BC5_DIRECT_EAGER_GPU_WRITE|BC5_DIRECT_DCC_PRESENT" "BC5_DIRECT_DCC_PRESENT=1" ;;
        cE2) arm cE2 a "BC5_DIRECT_EAGER_GPU_WRITE" "" ;;
        N0) arm N0 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_REGTAB_DUMP=$TD BC5_0439_REGTAB_AT=200,260" ;;
        N1) arm N1 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PUSH_NO_CLEAR=1 BC5_0439_PIECE_STATE_STACK=1" ;;
        N1a) arm N1a b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PUSH_NO_CLEAR=1" ;;
        N1b) arm N1b b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PIECE_STATE_STACK=1" ;;
        N2) arm N2 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        N3) arm N3 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_CENSUS=1 BC5_0439_COND_POP_NOP=1 BC5_0439_REGTAB_DUMP=$TD BC5_0439_REGTAB_AT=150,200" ;;
        D0) arm D0 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_CENSUS=1 BC5_0439_REGTAB_DUMP=$TD BC5_0439_REGTAB_AT=150,200" ;;
        N2r) arm N2r b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_CENSUS=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        N2d) arm N2d b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_CENSUS=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_REGTAB_DUMP=$TD BC5_0439_REGTAB_AT=150,200" ;;
        G1) arm G1 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_GUARDED=1 BC5_0439_COND_POP_NOP=1 BC5_0439_MLOCK_IMPORTS=1" ;;
        P0) ARM_PRESS="${CS_PRESS:-180 1500 90}" arm P0 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_GUARDED=1 BC5_0439_COND_POP_NOP=1" ;;
        P1) ARM_PRESS="${CS_PRESS:-180 1500 90}" arm P1 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_CC_GUARDED=1 BC5_0439_COND_POP_NOP=1 BC5_0439_MLOCK_IMPORTS=1" ;;
        # 11-24 ~19:40 (tag fn439, the top session's GO): the opening film from the title start (fresh empty save folder, no
        # keys), a shot every 2 s from 4 s, bound CS_BOUND (120 s for these); F3 forced CONTEXT_CONTROL, F0 PASS alone,
        # F1 PASS + MLOCK_IMPORTS, F2 PASS + COND_POP_NOP, F12 PASS + both (the pair he played); a trailing r = a repeat
        F3*|F0*|F1*|F2*) case $a in F3*) w="" ;; F0*) w="BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
                F12*) w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1 BC5_0439_COND_POP_NOP=1" ;;
                F1*) w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1" ;;
                F2*) w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_COND_POP_NOP=1" ;; esac
            ARM_SRC="" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 $w" ;;
        # 11-24 ~19:50 (fn439b): F0 (PASS) from the title start with one thing changed: FD in the distrobox (the 11-23 plays
        # ran there), FM with the old memlock limit 2.05 GiB, FS from a copy of his set-aside save of 11-23 22:33 (fn439-set-aside-1123-2233/TITLE3, a cp -a of it)
        FD) ARM_DB=1 ARM_SRC="" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm FD b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        FM) ARM_SDP="LimitMEMLOCK=2201170739" ARM_SRC="" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm FM b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        FS) ARM_SRC="$HOME/bc5-data/saves/fn439-set-aside-1123-2233" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm FS b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # fn439c: FL from a copy of his live save as it is now (fn439-live-1124, cp -a of ~/bc5-work/_SaveData/TITLE3), FSr = FS again
        FL) ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm FL b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        FSr) ARM_SRC="$HOME/bc5-data/saves/fn439-set-aside-1123-2233" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm FSr b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        F12L) ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm F12L b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1 BC5_0439_COND_POP_NOP=1" ;;
        F1L) ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm F1L b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1" ;;
        F2L) ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm F2L b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_COND_POP_NOP=1" ;;
        F0L33) ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm F0L33 b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # 11-24 night (tag vz439, priv34 = priv33 + the slot dump): the opening film from the title start with the slots
        # dumped (pictures VZ_K) into ~/bc5-data/priv/vz439/<arm>; VE an empty save folder, VL his live save copy, VS his 11-23 copy
        VE*|VL*|VS*) case $a in VE*) src="" ;; VL*) src="$HOME/bc5-data/saves/fn439-live-1124" ;; VS*) src="$HOME/bc5-data/saves/fn439-set-aside-1123-2233" ;; esac
            vd=$HOME/bc5-data/priv/vz439/$a-$(date +%H%M); mkdir -p "$vd" && chmod 700 "$HOME/bc5-data/priv/vz439" "$vd"
            ARM_FDS=1 ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_VD2_DUMP=${VZ_K:-60,120,180,240,300,360,450,600} BC5_0439_VD2_DUMP_DIR=$vd" ;;
        # vz439b: which part of his live save makes the film clean: VM only its sce_sdmemory (the save memory), VN all but it
        # VW: the save memory an empty-folder start wrote itself (VE 21:31, fn439-ve-own)
        VM*|VN*|VW*) case $a in VM*) src="$HOME/bc5-data/saves/fn439-sdmem-only" ;; VN*) src="$HOME/bc5-data/saves/fn439-no-sdmem" ;; VW*) src="$HOME/bc5-data/saves/fn439-ve-own" ;; esac
            ARM_FDS=0 ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439c: the flip-time DCC decompress off (DCC_PRESENT=1, log only) with the default-settings save (PW) and his (PL)
        PW|PL) case $a in PW) src="$HOME/bc5-data/saves/fn439-ve-own" ;; PL) src="$HOME/bc5-data/saves/fn439-live-1124" ;; esac
            ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=2 ARM_SHOT_FROM=4 arm "$a" b "$NB|BC5_DIRECT_DCC_PRESENT" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_DIRECT_DCC_PRESENT=1" ;;
        # vz439d: the frame dump (sr439b, BC5_0439_FRAME_DUMP in mw439's words) armed by a scripted L3+R3 hold at 3.5 s, on the
        # "presents" card: DW the default-settings save (noise), DL his save (clean)
        DW|DL) case $a in DW) src="$HOME/bc5-data/saves/fn439-ve-own" ;; DL) src="$HOME/bc5-data/saves/fn439-live-1124" ;; esac
            ARM_CMD="wait 3500|hold l3|hold r3|wait 1200|release l3|release r3" ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=1 ARM_SHOT_FROM=3 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439e: the pass census (sr439c) of the card frame, armed 3 s and 6 s after the first flip: CW default-settings save, CL his
        CW|CL) case $a in CW) src="$HOME/bc5-data/saves/fn439-ve-own" ;; CL) src="$HOME/bc5-data/saves/fn439-live-1124" ;; esac
            pd=$HOME/bc5-data/priv/passes; mkdir -p "$pd" && chmod 700 "$pd"
            ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=1 ARM_SHOT_FROM=2 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_PASS_DUMP=$pd BC5_0439_PASS_AT=${CS_PASS_AT:-3,6}" ;;
        # vz439f: SW the default-settings save with a 1 s SIGSTOP at ~8 s (no capture); SW2 the same at ~12 s
        SW|SW2) case $a in SW) st="8 1" ;; SW2) st="12 1" ;; esac
            ARM_STALL="$st" ARM_SRC="$HOME/bc5-data/saves/fn439-ve-own" ARM_ROUTE=0 ARM_SHOT_S=1 ARM_SHOT_FROM=2 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439g: LP the default-settings save with BC5_0439_FLIP_LABEL_PIECES=1 (vl439 (b): flip-label waits in chained pieces served on
        # the CPU), LPr a repeat, LPL his save with it
        LP|LPr|LPL) case $a in LPL) src="$HOME/bc5-data/saves/fn439-live-1124" ;; *) src="$HOME/bc5-data/saves/fn439-ve-own" ;; esac
            ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=1 ARM_SHOT_FROM=2 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_FLIP_LABEL_PIECES=1" ;;
        # vz439h (overnight 11-24/25): one save memory per graphics mode from the scripted save x439mwu-end (an empty start shows
        # no menus: film, title, then the overlook) through the new-game menus
        # (QUALITY is the screen's default; right once PERFORMANCE, twice RAY TRACING; check = the option name against the
        # refs), then play (a cross every 20 s) to the bound for gameplay shots; the run's save folder is the mode's memory
        MQ|MP|MR) case $a in MQ) rt="wait45 cross need=difficulty cross need=experience cross need=graphics right left check cross play"; w=quality ;; MP) rt="wait45 cross need=difficulty cross need=experience cross need=graphics right check cross play"; w=performance ;;
                MR) rt="wait45 cross need=difficulty cross need=experience cross need=graphics right right check cross play"; w=raytracing ;; esac
            ARM_RT="$rt" ARM_WANT="$w" ARM_SRC="$SRC" ARM_ROUTE=1 ARM_SHOT_S=10 ARM_SHOT_FROM=2 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439i: a title start from each mode's save memory (fn439-mode-q/p/r, copies of MQ/MP/MR's save folders) or an empty
        # folder (TE): shots every 1 s from 2 s for the film, the census armed 30 s after the first flip for the render size
        TQ|TP|TR|TE) case $a in TQ) src="$HOME/bc5-data/saves/fn439-mode-q" ;; TP) src="$HOME/bc5-data/saves/fn439-mode-p" ;; TR) src="$HOME/bc5-data/saves/fn439-mode-r" ;; TE) src="" ;; esac
            pd=$HOME/bc5-data/priv/passes; mkdir -p "$pd" && chmod 700 "$pd"
            ARM_SRC="$src" ARM_ROUTE=0 ARM_SHOT_S=1 ARM_SHOT_FROM=2 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_PASS_DUMP=$pd BC5_0439_PASS_AT=${CS_PASS_AT:-30} BC5_0439_PASS_MB=256" ;;
        # vz439h: MV a start driven by hand (live439.sh) for the settings menu: the input file on, no route, shots every 30 s
        MV*) ARM_CMD="wait 1" ARM_SRC="${MV_SRC:-}" ARM_ROUTE=0 ARM_SHOT_S=30 ARM_SHOT_FROM=10 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439k (overnight): GF a long scripted ride from a copy of his live save (the edge moves until the bound), shots every 30 s
        GF*) ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=30 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # vz439k (R74): the lean A/B of the flip-label fix, one binary for both arms (priv35's lean, pinned as k439/lean/
        # kyty_emulator.$CS_LEAN_PIN): LW0/LC? with BC5_0439_FLIP_LABEL_PIECES=0 (the zero arm), LF? with the default (on);
        # his live save, no keys, CS_BOUND s, MangoHud's frame log in raw/mh-<arm>
        LW0|LC*|LF*) case $a in LF*) w="" ;; *) w="BC5_0439_FLIP_LABEL_PIECES=0" ;; esac
            mkdir -p "$K/raw/mh-$a"
            ARM_PIN="${CS_LEAN_PIN:?}" ARM_LEAN=1 ARM_MH="$K/raw/mh-$a" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=0 ARM_SHOT_S=60 ARM_SHOT_FROM=60 arm "$a" b "$NB" "BC5_0439_PASS_CONTEXT_CONTROL=1 $w" ;;
        # vz439m (step 3): the growth census on the route that reached 11.9 GB: a title start from an empty folder, the
        # cross at 45 s into the overlook, then the edge moves to the bound; BC5_0439_MG_CENSUS=1 every 10 s
        GM*) ARM_RT="wait45 cross wait60 cross edge" ARM_SRC="" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=30 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MG_CENSUS=1" ;;
        # sn439: GS = GF (20-min ride from his save copy) with the memory budget snapshots every 30 s
        GS*) ARM_SNAP=1 ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=1 ARM_SHOT_S=60 ARM_SHOT_FROM=30 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # step 5 (rainbow patches): RQ/RP/RR a ride from his live save with the Quality / Performance / Ray Tracing save memory
        # (fn439-live-q/p/r: the copy with sce_sdmemory replaced), the edge moves, a shot every 10 s
        RQ|RP|RR) case $a in RQ) src="$HOME/bc5-data/saves/fn439-live-q" ;; RP) src="$HOME/bc5-data/saves/fn439-live-p" ;; RR) src="$HOME/bc5-data/saves/fn439-live-r" ;; esac
            ARM_RT="wait40 edge" ARM_SRC="$src" ARM_ROUTE=1 ARM_SHOT_S=10 ARM_SHOT_FROM=40 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # step 5b: RP2/RQ2/RR2 the same rides with a shot every 2 s from 60 s (the patches seen at RP t90), bound CS_BOUND
        RP2|RQ2|RR2) case $a in RQ2) src="$HOME/bc5-data/saves/fn439-live-q" ;; RP2) src="$HOME/bc5-data/saves/fn439-live-p" ;; RR2) src="$HOME/bc5-data/saves/fn439-live-r" ;; esac
            ARM_RT="wait40 edge" ARM_SRC="$src" ARM_ROUTE=1 ARM_SHOT_S=2 ARM_SHOT_FROM=60 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1" ;;
        # gv439: GV1 the title-start route of GM (300 s), GV2 the 20-min ride from his save copy, both with the mg439 and gv439 censuses
        GV1) ARM_RT="wait45 cross wait60 cross edge" ARM_SRC="" ARM_ROUTE=1 ARM_SHOT_S=60 ARM_SHOT_FROM=30 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MG_CENSUS=1 BC5_0439_GV_CENSUS=1" ;;
        GV2) ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=1 ARM_SHOT_S=60 ARM_SHOT_FROM=30 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MG_CENSUS=1 BC5_0439_GV_CENSUS=1" ;;
        # vt439: RBP a ride in Performance (his save with the Performance memory) with the rainbow trigger at CS_RB_N (3) of 4096, a shot every 10 s
        RBP*) ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-p" ARM_ROUTE=1 ARM_SHOT_S=10 ARM_SHOT_FROM=40 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_RB_TRIGGER=${CS_RB_N:-3}" ;;
        # fr439 (11-25, the top session's separation of the 19:01 freeze): his save copy, the ride, guard at 1,200 MB available or IO
        # full avg10 > 1.5; FA = t3-test-all.sh 50b6c182's configuration (priv33 c0ec7b38, its exact words: the slot's base minus
        # EAGER_GPU_WRITE, NO_MERGE, VA_DEFER, GUARD_LEDGER, plus PASS + MLOCK_IMPORTS + COND_POP_NOP), FB = FA without MLOCK, FC = FA
        # without COND_POP_NOP, QD = priv35 138e6779 (FD was taken by fn439b) with t3-test-fl.sh's words (PASS + FLIP_LABEL_PIECES=1)
        FA|FB|FC|QD) case $a in FA) pin=c0ec7b38; w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1 BC5_0439_COND_POP_NOP=1" ;;
                FB) pin=c0ec7b38; w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_COND_POP_NOP=1" ;; FC) pin=c0ec7b38; w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_MLOCK_IMPORTS=1" ;;
                QD) pin=138e6779; w="BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_FLIP_LABEL_PIECES=1" ;; esac
            ARM_GUARD_MB=1200 ARM_GUARD_IO=1.5 ARM_PIN=$pin ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=30 \
                arm "$a" b "BC5_DIRECT_EAGER_GPU_WRITE|BC5_0439_NO_MERGE|BC5_0439_VA_DEFER|BC5_GUARD_LEDGER" "$w" ;;
        # vt439b: VTP a Performance ride with the trigger from 60 s at CS_RB_N (10) and the frame dump armed by it (RB_ARM=1)
        VTP*) ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-p" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=40 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_RB_TRIGGER=${CS_RB_N:-10} BC5_0439_RB_FROM=60 BC5_0439_RB_ARM=1" ;;
        # fl439: WC* a Performance ride with the catcher (the trigger from 60 s at 10, the ring written at 100+), fix off; WF* the same with
        # BC5_0439_FLIP_WAIT_PENDING=1
        WC*|WF*) case $a in WF*) fx="BC5_0439_FLIP_WAIT_PENDING=1" ;; *) fx="" ;; esac
            ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-p" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=40 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_RB_TRIGGER=10 BC5_0439_RB_FROM=60 BC5_0439_FL_CATCH=1 $fx" ;;
        # io439: IOD the D configuration (priv35 normal 138e6779, t3-test-fl's words) with the IO sampler, 1,200 s; IOL priv35's lean
        # 2d08049d with the same words, no logs (BC5_LOGS=0, no PLAY_CAPTURE, no FRAME_DUMP or RUN_ENV), the same sampler
        IOD|IOL) case $a in IOD) pin=138e6779; ln=0; lg=1; dr="" ;; IOL) pin=2d08049d; ln=1; lg=0; dr="|BC5_0439_FRAME_DUMP|BC5_RUN_ENV" ;; esac
            ARM_IO=1 ARM_LOGS=$lg ARM_CAPTURE=$lg ARM_LEAN=$ln ARM_PIN=$pin ARM_GUARD_MB=1200 ARM_GUARD_IO=1.5 ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-1124" ARM_ROUTE=1 ARM_SHOT_S=60 ARM_SHOT_FROM=30                 arm "$a" b "BC5_DIRECT_EAGER_GPU_WRITE|BC5_0439_NO_MERGE|BC5_0439_VA_DEFER|BC5_GUARD_LEDGER$dr" "BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_FLIP_LABEL_PIECES=1" ;;
        # fl439b: WB* the WF ride with the bound raised to 2,000 ms (BC5_0439_FLIP_WAIT_MS=2000) and the wait-pending fix
        WB*) ARM_RT="wait40 edge" ARM_SRC="$HOME/bc5-data/saves/fn439-live-p" ARM_ROUTE=1 ARM_SHOT_S=30 ARM_SHOT_FROM=40 arm "$a" b "$NB" "BC5_0439_CS_COUNT=1 BC5_0439_PASS_CONTEXT_CONTROL=1 BC5_0439_RB_TRIGGER=10 BC5_0439_RB_FROM=60 BC5_0439_FL_CATCH=1 BC5_0439_FLIP_WAIT_PENDING=1 BC5_0439_FLIP_WAIT_MS=2000" ;;
        *) echo "unknown arm $a" ;;
    esac
done
echo "slot439cs: $(date +%T) done; GPU kernel lines $g_start -> $(gl); binary $P"
