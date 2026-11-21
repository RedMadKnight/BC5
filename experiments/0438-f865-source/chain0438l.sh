#!/usr/bin/env bash
# BC5 experiment 0438, the lean round (top session 2026-11-20): b438 (r438 alone on patch bb04219b's unit) in its lean
# and normal builds, his 09:46 scene (the read-only snapshot, slot 4, no input after the load, G+$PLAY), RT on, way 2's
# words. Every arm runs the same way: run0438l.sh (exp 0432's scene runner with exp 0430's N_MH / N_LEANSESS hunks),
# the route BY TIME (N_TIMED: cross 90 s, slot 4 at +8, Continue at +8, G at +20), MangoHud's own per-frame log as the
# one frame counter (N_MH, written at N_MHD s of its own clock, before the runner ends the run), the Plasma shell stopped for the run as the lean shortcuts do
# (N_LEANSESS), the ubuntu distrobox. Arms (the binary and BC5_0438_EARLYREG, nothing else differs):
#   L0  lean b438, EARLYREG=0 (control)
#   L1p lean b438, EARLYREG=1 PLWCV=0 (r438 with its 20-us poll)   L1c lean b438, EARLYREG=1 PLWCV=1 (r438, condition variable)
#   LP  lean b438, EARLYREG=1 PLWCV=1 PROLMERGE=1 (L1c + p438's prologue merge); every other arm has PROLMERGE=0
#   H   normal h438 (the bake unit + h438 + o438) with BC5_0438_HOSTWAIT=1 BC5_0438_OUTSIDE=1, the per-frame CSV in
#       $RAW/$t-h438.csv: DIAGNOSIS ONLY, as O
#   F   normal fm438 (h438 + f438 + m438) with BC5_0438_HOSTWAIT=1 BC5_0438_OUTSIDE=1 BC5_0438_FRAMEMARK=1, prof0438.sh
#       beside it from G in PROF_MODE=faults (every page fault of the Render Thread, with its address): DIAGNOSIS ONLY
#   P   lean m438 (the bake unit + m438) with BC5_0438_FRAMEMARK=1, prof0438.sh in PROF_MODE=cpu (cpu-clock 999 Hz on the
#       Render Thread): DIAGNOSIS ONLY (a profiled run is not a speed measurement)
#   S   the SHARED lean build itself (no extra word), prof0438.sh in PROF_MODE=all (every thread at 199 Hz, per-thread
#       schedstat every second): which threads run and wait while the Render Thread spins. DIAGNOSIS ONLY
#   K   the SHARED lean build, prof0438.sh in PROF_MODE=stacks (game-main's call chains, the Render Thread's samples):
#       DIAGNOSIS ONLY
#   M   the SHARED lean build with LD_PRELOAD=cpy438.so (the large memcpy/memmove callers, $RAW/$t-cpy.<pid>.txt) and
#       prof0438.sh in PROF_MODE=cpu (the Render Thread's samples, for the spins): DIAGNOSIS ONLY
#   O   normal b438 with BC5_0438_OUTSIDE=1: DIAGNOSIS ONLY (where the Render Thread waits, who wakes it). The
#       maintainer's rule (2026-11-20): performance numbers come from lean builds only; no fps or frame time is reported
#       for a normal-build run (its row and line say "diagnosis").
# Per run: the binary that ran (R66), pad keys (R51), flips/s and gap seconds from MangoHud's per-second lines from
# G+10, the MangoHud CSV kept in $RAW/$t-mh/ (mh0438.py computes median / p95 / p99 frame time on the laptop), and for a
# normal arm the r438 line and BUG count from its journal. Stops: a class other than NO_CRASH (R55), a wrong binary, a
# BOX-LOCK that is not ours, an emulator that is not ours, GPU lines grown, ~/bc5-work/exp0438/STOP. Gate: the first L0's
# flips/s >= 33.3. Each run takes and frees its own BOX-LOCK line (the runner).
# usage (on the box, under the user manager, from ~/bc5-work/exp0438/kit):
#   ORDER="L0 L1p L1c LP L0 L1p L1c LP L0 L1p L1c LP O O" K0=<last run number> bash chain0438l.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0438; HERE=$(cd "$(dirname "$0")" && pwd)
k=${K0:?the last run number}; PLAY=${PLAY:-300}
SB=$W/kytyplus-build/src/kyty_emulator; SL=$W/kytyplus-build-lean/src/kyty_emulator
LB=$E/b438/lean/kyty_emulator; NB=$E/b438/normal/kyty_emulator; HB=$E/h438/normal/kyty_emulator
HW=$(cat "$E/h438/normal/binary.md5" 2> /dev/null)
FB=$E/fm438/normal/kyty_emulator; FW=$(cat "$E/fm438/normal/binary.md5" 2> /dev/null)
PB=$E/fm438/lean/kyty_emulator; PW=$(cat "$E/fm438/lean/binary.md5" 2> /dev/null)
PROF=$HERE/prof0438.sh
LW=$(cat "$E/b438/lean/binary.md5" 2> /dev/null); NW=$(cat "$E/b438/normal/binary.md5" 2> /dev/null)
WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3 BC5_DIRECT_TIMEOUT_PROBE=1"
RUN=$HERE/run0438l.sh; RAW=$W/exp0432/n/raw
SNAP=$HOME/bc5-data/saves/PPSA03671-20261117-0946-play
OUT=$E/chain-l-rows.txt
say() { echo "chain0438l $(date +%T): $*"; }
[ -d "$SNAP/PPSA03671" ] && [ ! -L "$SNAP" ] || { say "NOT STARTED, no $SNAP/PPSA03671"; exit 1; }
[ "$(md5sum < "$SB" | cut -c1-8)" = b1b57df9 ] && [ "$(md5sum < "$SL" | cut -c1-8)" = d3485ed4 ] || { say "NOT STARTED, the shared builds are not b1b57df9 / d3485ed4"; exit 1; }
[ -n "$LW" ] && [ "$(md5sum < "$LB" | cut -d' ' -f1)" = "$LW" ] && [ -n "$NW" ] && [ "$(md5sum < "$NB" | cut -d' ' -f1)" = "$NW" ] || { say "NOT STARTED, b438's binaries do not match their binary.md5"; exit 1; }
case " $ORDER " in *" F "* | *" P "*) [ -n "$FW" ] && [ "$(md5sum < "$FB" | cut -d' ' -f1)" = "$FW" ] && [ -n "$PW" ] && [ "$(md5sum < "$PB" | cut -d' ' -f1)" = "$PW" ] && [ -s "$PROF" ] || { say "NOT STARTED, fm438's binaries or prof0438.sh do not match"; exit 1; } ;; esac
case " $ORDER " in *" H "*) [ -n "$HW" ] && [ "$(md5sum < "$HB" | cut -d' ' -f1)" = "$HW" ] || { say "NOT STARTED, h438's binary does not match its binary.md5"; exit 1; } ;; esac
[ "$(md5sum < "$RUN" | cut -c1-8)" = "${K_RUN:-7c6da668}" ] || { say "NOT STARTED, run0438l.sh is not ${K_RUN:-7c6da668}"; exit 1; }
[ -s "$WORDS" ] || { say "NOT STARTED, no $WORDS"; exit 1; }
say "play $PLAY s, order ${ORDER:?}; lean ${LW:0:8}, normal ${NW:0:8}; runner $(md5sum < "$RUN" | cut -c1-8); kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
PADS=()
padon() { : > "$E/raw/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$E/raw/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
trap padoff EXIT
mkdir -p "$E/raw"
gpucount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
export R0438_BASE; R0438_BASE=$(gpucount)
say "GPU timeout/reset lines since boot at the chain's start: $R0438_BASE"
for arm in $ORDER; do
  k=$((k + 1))
  case "$arm" in
    L0) bin=$LB; want=$LW; AW="BC5_0438_EARLYREG=0 BC5_0438_PROLMERGE=0" ;;
    L1p) bin=$LB; want=$LW; AW="BC5_0438_EARLYREG=1 BC5_0438_PLWCV=0 BC5_0438_PROLMERGE=0" ;;
    L1c) bin=$LB; want=$LW; AW="BC5_0438_EARLYREG=1 BC5_0438_PLWCV=1 BC5_0438_PROLMERGE=0" ;;
    LP) bin=$LB; want=$LW; AW="BC5_0438_EARLYREG=1 BC5_0438_PLWCV=1 BC5_0438_PROLMERGE=1" ;;
    O)  bin=$NB; want=$NW; AW="BC5_0438_EARLYREG=0 BC5_0438_PROLMERGE=0 BC5_0438_OUTSIDE=1" ;;
    H)  bin=$HB; want=$HW; AW="BC5_0438_HOSTWAIT=1 BC5_0438_OUTSIDE=1" ;;
    F)  bin=$FB; want=$FW; AW="BC5_0438_HOSTWAIT=1 BC5_0438_OUTSIDE=1 BC5_0438_FRAMEMARK=1" ;;
    P)  bin=$PB; want=$PW; AW="BC5_0438_FRAMEMARK=1" ;;
    S)  bin=$SL; want=$(md5sum < "$SL" | cut -d' ' -f1); AW="" ;;
    K)  bin=$SL; want=$(md5sum < "$SL" | cut -d' ' -f1); AW="" ;;
    M)  bin=$SL; want=$(md5sum < "$SL" | cut -d' ' -f1); AW="LD_PRELOAD=$E/cpy/cpy438.so" ;;
    *) say "arm $arm: L0, L1p, L1c, LP, H, F, P, S, K, M or O (N0 dropped: no performance numbers from normal builds)"; break ;;
  esac
  t=b438$arm$k; while [ -e "$RAW/$t-start.txt" ] || [ -e "$RAW/$t-end.txt" ]; do t=${t}b; done
  [ "$arm" = H ] && AW="$AW BC5_0438_HOSTWAIT_FILE=$RAW/$t-h438.csv"
  [ "$arm" = F ] && AW="$AW BC5_0438_HOSTWAIT_FILE=$RAW/$t-h438.csv BC5_0438_FRAMEMARK_FILE=$RAW/$t-m438.txt"
  [ "$arm" = P ] && AW="$AW BC5_0438_FRAMEMARK_FILE=$RAW/$t-m438.txt"
  [ "$arm" = M ] && AW="$AW CPY438_OUT=$RAW/$t-cpy"
  SIDE=""; PMODE=""; case "$arm" in F) SIDE=$PROF; PMODE=faults ;; P) SIDE=$PROF; PMODE=cpu ;; S) SIDE=$PROF; PMODE=all ;; K) SIDE=$PROF; PMODE=stacks ;; M) SIDE=$PROF; PMODE=cpu ;; esac
  [ -e "$E/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  [ -s "$W/BOX-LOCK" ] && { say "a BOX-LOCK line before $t that is not a run of ours: $(cat "$W/BOX-LOCK"): stop"; break; }
  [ "$(gpucount)" = "$R0438_BASE" ] || { say "GPU timeout/reset lines grew from $R0438_BASE to $(gpucount) before $t: stop"; break; }
  say "run $t, arm $arm, ${want:0:8}"
  : > "$E/raw/$t-t0"
  padon "$t"
  ( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done
    if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$E/raw/$t-exe.txt" 2>&1 &
  XP=$!
  # shellcheck disable=SC2086
  line=$(env N_SIDE="$SIDE" PROF_MODE="$PMODE" N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1 N_TIMED=1 N_T0=90 N_T1=8 N_T2=8 N_T3=20 N_MH=1 N_MHD=$((126 + PLAY - 15)) N_LEANSESS=1 N_FUSE=0 N_NOWD=1 \
    P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$RUN" "$t" h "$PLAY" $WAY2 $AW | grep "^$t ")
  padoff; wait "$XP" 2> /dev/null
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  G=$(sed -n 's/.*; G \([0-9]*\),.*/\1/p' "$RAW/$t-end.txt" 2> /dev/null)
  FPS=$(awk -v g="${G:-999999}" 'NF == 4 && $1 >= g + 10 {s += $3; f += $2; if ($4 > 50) a++; if ($4 > 100) b++} END {if (s > 0) printf "%.2f flips/s over %d s from G+10, %d s with a frame over 50 ms, %d over 100 ms", f / s, s, a, b; else printf "no fps lines after G+10"}' "$RAW/$t-fps.txt" 2> /dev/null)
  EXE=$(cat "$E/raw/$t-exe.txt" 2> /dev/null); PADN=$(grep -c . "$E/raw/$t-pad.txt" 2> /dev/null)
  MHF=$(ls -t "$RAW/$t-mh"/*.csv 2> /dev/null | grep -v summary | head -1)
  SU="MangoHud ${MHF:-none} ($( [ -n "$MHF" ] && wc -l < "$MHF" || echo 0) lines); lean lost-write lines $(grep -ac 'r438 (exp 0438, b438, lean)' "$RAW/$t-play.log" 2> /dev/null)"
  case "$arm" in O | H | F | P | S | K | M) FPS="diagnosis run: no fps or frame time reported (lean-only rule)" ;; esac
  [ "$arm" = S ] && SU="$SU; prof [$(tail -1 "$RAW/$t-prof-perf.log" 2> /dev/null)]; threads lines $(wc -l < "$RAW/$t-prof-threads.txt" 2> /dev/null || echo 0)"
  case "$arm" in F | P) SU="$SU; m438 $(wc -l < "$RAW/$t-m438.txt" 2> /dev/null || echo 0) marks; prof [$(tail -1 "$RAW/$t-prof-perf.log" 2> /dev/null)]" ;; esac
  [ "$arm" = F ] && SU="$SU; h438 csv $(wc -l < "$RAW/$t-h438.csv" 2> /dev/null || echo 0) lines; f438 lines $(grep -ac '^f438 (exp 0438)' "$RAW/$t-play.log" 2> /dev/null)"
  [ "$arm" = H ] && SU="$SU; h438 csv $(wc -l < "$RAW/$t-h438.csv" 2> /dev/null || echo 0) lines"
  if [ "$arm" = O ] || [ "$arm" = H ] || [ "$arm" = F ]; then
    PD=$(ls -dt "$HOME"/bc5-data/captures/play-*/ 2> /dev/null | head -1); DL=${PD}gc/direct.log
    if [ -n "$PD" ] && [ -f "$DL" ] && [ "$DL" -nt "$E/raw/$t-t0" ]; then
      SU="$SU; log $DL; GIVEN UP $(grep -ac 'GIVEN UP' "$DL"); r438 [$(grep -a '^r438 (exp 0438, b438): t ' "$DL" | tail -1 | cut -c1-500)], r438 BUG lines $(grep -ac '^r438 (exp 0438, b438): BUG' "$DL"); p438 [$(grep -a '^p438 (exp 0438): t ' "$DL" | tail -1 | cut -c1-300)]; o438 lines $(grep -ac '^o438 (exp 0438)' "$RAW/$t-play.log" 2> /dev/null)"
    else SU="$SU; no direct.log of this run found"; fi
  fi
  echo "$t $arm [$AW] ${CLASS:-NONE} | $FPS | exe [$EXE] | pad keys $PADN | [$SU] | $(printf '%s\n' "$line" | cut -c1-300)" >> "$OUT"
  say "$t: ${CLASS:-NONE}; $FPS; pad keys $PADN"
  case "$EXE" in *" md5 $want") ;; *) say "$t ran another binary than ${want:0:8} ($EXE): stop"; break ;; esac
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "class ${CLASS:-NONE}: stop (R55; the records are the result)"; break; }
  if [ "$arm" = L0 ] && [ -z "${GATE_DONE:-}" ]; then
    GATE_DONE=1; f=$(printf '%s\n' "$FPS" | sed -n 's/^\([0-9.]*\) flips.*/\1/p')
    awk -v f="${f:-0}" 'BEGIN {exit !(f >= 33.3)}' || { say "first L0 at ${f:-?} flips/s is under the gate 33.3: stop"; break; }
  fi
  sleep 20
done
say "chain ended"
