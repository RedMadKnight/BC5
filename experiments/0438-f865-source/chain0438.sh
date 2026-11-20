#!/usr/bin/env bash
# BC5 experiment 0438 (F865, tag k438): exp 0436's chain0436.sh with exp 0438's test build as the candidate (C, its switch
# BC5_0438_KEEP=1 by default in the binary) and the shared normal f345db74 (patch bb04219b) as S. Scene mode is the test.
#   MODE=route  exp 0430's run0430f.sh as exp 0433's chain0433.sh calls it: slot 4 of exp 0425's named snapshot, the
#               maintainer's 14:50 fight record at G, then exp 0379's walk to G+$PLAY (default 1500); way 2's words named;
#               JobArenaFix off (N_ARENA=off); no fuse, no memory watchdog.
#   MODE=scene  exp 0432's run0432f.sh as scene0432.sh calls it: his 09:46 scene (the read-only snapshot
#               ~/bc5-data/saves/PPSA03671-20261117-0946-play), slot 4, no input after the load, G+$PLAY (default 300).
# Both arms get the same words (way 2's five, BC5_DIRECT_TIMEOUT_PROBE=1 for a fault's record); the arm is the binary
# alone (the candidate's switch is on in its test build unless =0). RT on as the title's settings hold it.
# Per run, beside the runner: the emulator's /proc/<pid>/exe and its md5 once it starts (LESSONS R66: the binary that
# really ran), the pad's key events (R51: a key = the run is void as a measurement), and after the run flips/s and the
# seconds with a gap over 50 / 100 ms from G+10 s (the runner's fps lines). Each run takes and frees its own BOX-LOCK
# line (the runner). Stops: a class other than NO_CRASH (R55), a wrong binary, ~/bc5-work/exp0438/STOP (read before each
# run), an emulator that is not ours.
# usage (on the box, detached under the user manager, from ~/bc5-work/exp0438/kit):
#   MODE=route ORDER="C S C S C S" K0=0 bash chain0438.sh   (tags u438<r|s><S|C><k>)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0438; HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${MODE:?route or scene}; k=${K0:?the last run number}
SB=$W/kytyplus-build/src/kyty_emulator; CB=$E/normal/kyty_emulator
SW=$(md5sum < "$SB" | cut -d' ' -f1); CW=$(cat "$E/normal/binary.md5")
WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3 BC5_DIRECT_TIMEOUT_PROBE=1"
OUT=$E/chain-rows.txt
say() { echo "chain0438 $(date +%T): $*"; }
case "$MODE" in
  route) RUN=${ROUTE_RUN:-$W/exp0430/run0430f.sh};  # the original on a clean boot; ROUTE_RUN=$HERE/run0430f-0436.sh on a boot with old resets (ruling 2026-11-20)
  RAW=$W/exp0430/n/raw; PLAY=${PLAY:-1500}; RENV="N_ARENA=off N_WALK_AFTER=1 N_SLOT=4"; mt=r ;;
  scene) RUN=$W/exp0432/kit/run0432f.sh; RAW=$W/exp0432/n/raw; PLAY=${PLAY:-300}; SNAP=$HOME/bc5-data/saves/PPSA03671-20261117-0946-play
         [ -d "$SNAP/PPSA03671" ] && [ ! -L "$SNAP" ] || { say "NOT STARTED, no $SNAP/PPSA03671"; exit 1; }
         RENV="N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1"; mt=s ;;
  *) say "MODE is route or scene"; exit 1 ;;
esac
[ "${SW:0:8}" = f345db74 ] || { say "NOT STARTED, the shared normal is ${SW:0:8}, not f345db74"; exit 1; }
[ "$(md5sum < "$CB" | cut -d' ' -f1)" = "$CW" ] || { say "NOT STARTED, $CB is not ${CW:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$RUN" ] || { say "NOT STARTED, no $WORDS or $RUN"; exit 1; }
say "mode $MODE, play $PLAY s, order ${ORDER:-S C S C S C}; shared ${SW:0:8}, candidate ${CW:0:8}; runner $(md5sum < "$RUN" | cut -c1-8); kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
PADS=()
padon() { : > "$E/raw/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$E/raw/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
trap padoff EXIT
mkdir -p "$E/raw"
# The amdgpu timeout/reset lines since boot are the baseline (0 expected on a clean boot); the chain stops if it grows.
gpucount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
export R0438_BASE; R0438_BASE=$(gpucount)
say "GPU timeout/reset lines since boot at the chain's start: $R0438_BASE (the baseline; the route runner refuses on any other count)"
for arm in ${ORDER:-S C S C S C}; do
  k=$((k + 1))
  # arms (top, 2026-11-20): C = the test build with both candidates off, K = k438 only, KV = k438 + exp 0437's vg437; S = shared
  case "$arm" in S) bin=$SB; want=$SW; AW="" ;; C) bin=$CB; want=$CW; AW="BC5_0438_KEEP=0 BC5_0438_HOLD=0 BC5_DIRECT_VIEWS_GEN=0" ;;
    K) bin=$CB; want=$CW; AW="BC5_0438_KEEP=1 BC5_DIRECT_VIEWS_GEN=0" ;;
    V) bin=$CB; want=$CW; AW="BC5_0438_KEEP=0 BC5_0438_HOLD=0 BC5_DIRECT_VIEWS_GEN=1" ;;
    H) bin=$CB; want=$CW; AW="BC5_0438_KEEP=0 BC5_0438_HOLD=1 BC5_DIRECT_VIEWS_GEN=0" ;; HV) bin=$CB; want=$CW; AW="BC5_0438_KEEP=0 BC5_0438_HOLD=1 BC5_DIRECT_VIEWS_GEN=1" ;;
    C2) bin=$CB; want=$CW; AW="BC5_0438_KEEP=0 BC5_0438_HOLD=0 BC5_DIRECT_VIEWS_GEN=0" ;; KV) bin=$CB; want=$CW; AW="BC5_0438_KEEP=1 BC5_DIRECT_VIEWS_GEN=1" ;;
    *) say "arm $arm: S, C, C2, K, KV, V, H or HV"; break ;; esac
  t=u438$mt$arm$k; while [ -e "$RAW/$t-start.txt" ] || [ -e "$RAW/$t-end.txt" ]; do t=${t}b; done
  [ -e "$E/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  [ -s "$W/BOX-LOCK" ] && { say "a BOX-LOCK line before $t that is not a run of ours: $(cat "$W/BOX-LOCK"): stop"; break; }
  [ "$(gpucount)" = "$R0438_BASE" ] || { say "GPU timeout/reset lines grew from $R0438_BASE to $(gpucount) before $t: stop"; break; }
  say "run $t, arm $arm, ${want:0:8}"
  : > "$E/raw/$t-t0"  # the run's start mark: its capture directory's direct.log is newer than it
  padon "$t"
  ( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done  # the binary that runs (R66)
    if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$E/raw/$t-exe.txt" 2>&1 &
  XP=$!
  # shellcheck disable=SC2086
  line=$(env $RENV N_FUSE=0 N_NOWD=1 P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$RUN" "$t" h "$PLAY" $WAY2 $AW | grep "^$t ")
  padoff; wait "$XP" 2> /dev/null
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  G=$(sed -n 's/.*; G \([0-9]*\),.*/\1/p' "$RAW/$t-end.txt" 2> /dev/null)
  FPS=$(awk -v g="${G:-999999}" 'NF == 4 && $1 >= g + 10 {s += $3; f += $2; if ($4 > 50) a++; if ($4 > 100) b++} END {if (s > 0) printf "%.2f flips/s over %d s from G+10, %d s with a gap over 50 ms, %d over 100 ms", f / s, s, a, b; else printf "no fps lines after G+10"}' "$RAW/$t-fps.txt" 2> /dev/null)
  EXE=$(cat "$E/raw/$t-exe.txt" 2> /dev/null); PADN=$(grep -c . "$E/raw/$t-pad.txt" 2> /dev/null)
  PD=$(ls -dt "$HOME"/bc5-data/captures/play-*/ 2> /dev/null | head -1); DL=${PD}gc/direct.log
  if [ -n "$PD" ] && [ -f "$DL" ] && [ "$DL" -nt "$E/raw/$t-t0" ]; then
    SU="log $DL; GIVEN UP $(grep -ac 'GIVEN UP' "$DL"); k438 lines $(grep -ac '^k438 (exp 0438)' "$DL"); k438b [$(grep -a '^hold tail (exp 0438, k438b): [0-9]* holds' "$DL" | tail -1 | cut -c1-400)], STILL HELD $(grep -ac 'STILL HELD' "$DL"); last 60-s: $(grep -a '^ho430 (exp 0430): t' "$DL" | tail -1 | grep -o 'F4 fences [0-9]*\|F2 cycles left as they are [0-9]*\|k438 .*' | tr '\n' ' ')"
    SU="$SU; vg437 [$(grep -a '^exp 0437 (tag vg437)' "$DL" | tail -1)]"
    SU="$SU; frames (frame profile, last 290 s of the journal) $(grep -a '^frame profile: t' "$DL" | awk '{t=$4+0; g=$6+0; T[NR]=t; G[NR]=g} END {e=T[NR]; for (i=1;i<=NR;i++) if (T[i] >= e-290) {n++; if (G[i]>50) a++; if (G[i]>100) b++} printf "%d, over 50 ms %d, over 100 ms %d", n, a, b}')"
  else SU="no direct.log of this run found"; fi
  echo "$t $arm [$AW] ${CLASS:-NONE} | $FPS | exe [$EXE] | pad keys $PADN | journal [$SU] | $(printf '%s\n' "$line" | cut -c1-300)" >> "$OUT"
  say "$t: ${CLASS:-NONE}; $FPS; pad keys $PADN"
  case "$SU" in *"STILL HELD 0"*|*"no direct.log"*) ;; *"STILL HELD"*) say "$t: FLAG: a hold reached a STILL HELD record (a bug; the run ended normally, the record is kept)";; esac
  case "$EXE" in *" md5 $want") ;; *) say "$t ran another binary than ${want:0:8} ($EXE): stop"; break ;; esac
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "class ${CLASS:-NONE}: stop (R55; the records are the result)"; break; }
  # the top session's gate on a boot with a reset (2026-11-20): the chain's first C must match u438sC1 (36.91 flips/s, NO_CRASH)
  if { [ "$arm" = C ] || [ "$arm" = C2 ]; } && [ -z "${C_GATE_DONE:-}" ]; then
    C_GATE_DONE=1; f=$(printf '%s\n' "$FPS" | sed -n 's/^\([0-9.]*\) flips.*/\1/p')
    awk -v f="${f:-0}" 'BEGIN {exit !(f >= 33.3)}' || { say "first C at ${f:-?} flips/s is under the gate 33.3 (the low end of 0436's clean-boot scene range; top 2026-11-20): stop"; break; }
  fi
  sleep 20
done
say "chain ended"
