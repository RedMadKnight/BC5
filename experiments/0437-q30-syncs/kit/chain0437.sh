#!/usr/bin/env bash
# BC5 experiment 0437 (tag vg437): the candidate's normal test build with its switch on (arm V) against the SAME binary
# with BC5_DIRECT_VIEWS_GEN=0 (arm Z, the control: the shared behaviour exactly), alternating, one run at a time.
# After exp 0436's chain0436.sh; the arm is the word, the binary is one (the top session's arms, 2026-11-20).
#   MODE=route  exp 0430's run0430f.sh as chain0436.sh calls it: slot 4 of exp 0425's named snapshot, the maintainer's
#               14:50 fight record at G, then exp 0379's walk to G+$PLAY (default 1500); JobArenaFix off; no fuse, no
#               memory watchdog. ROUTE_RUN=<exp 0436's run0430f-0436.sh> on a boot with old resets (baseline gate).
#   MODE=scene  exp 0432's run0432f.sh: his 09:46 scene (the read-only snapshot ~/bc5-data/saves/TITLE2-20261117-0946-play),
#               slot 4, no input after the load, G+$PLAY (default 300).
# Both arms: way 2's words, BC5_DIRECT_TIMEOUT_PROBE=1, exp 0413's words file; RT on as the title's settings hold it; 4
# rings (BC5_DIRECT_ACB_RINGS=4). Per run, beside the runner: the emulator's /proc/<pid>/exe and md5 (R66), the pad's key
# events (R51), flips/s and the seconds with a gap over 50 / 100 ms from G+10 s, the run's vg437 line (view builds, the
# range table and direct generations) and an extract of its journal (frame profile, timing split, d432 and vg437 lines)
# into raw/<tag>-sync.txt.gz for split0437.py / frames0437.py. Stops: a class other than NO_CRASH (R55), a wrong binary,
# a missing or wrong vg437 state line, ~/bc5-work/exp0437/STOP, an emulator that is not ours, a BOX-LOCK line that is not
# a run of ours, new GPU timeout/reset lines, the hours 07:00-12:00 unless DAY_OK=1 (only with the top session's GO).
# usage (on the box, detached under the user manager, from ~/bc5-work/exp0437/kit):
#   systemd-run --user --scope -- env MODE=scene ORDER="V Z V Z V Z" K0=0 bash chain0437.sh     (tags u437<s|r><V|Z><k>)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0437; HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${MODE:?route or scene}; k=${K0:?the last run number}
SB=$W/kytyplus-build/src/kyty_emulator; CB=$E/normal/kyty_emulator
SW=$(md5sum < "$SB" | cut -d' ' -f1); CW=$(cat "$E/normal/binary.md5")
WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3 BC5_DIRECT_TIMEOUT_PROBE=1"
OUT=$E/chain-rows.txt
say() { echo "chain0437 $(date +%T): $*"; }
case "$MODE" in
  route) RUN=${ROUTE_RUN:-$W/exp0430/run0430f.sh}; RAW=$W/exp0430/n/raw; PLAY=${PLAY:-1500}; RENV="N_ARENA=off N_WALK_AFTER=1 N_SLOT=4"; mt=r ;;
  scene) RUN=$W/exp0432/kit/run0432f.sh; RAW=$W/exp0432/n/raw; PLAY=${PLAY:-300}; SNAP=$HOME/bc5-data/saves/TITLE2-20261117-0946-play
         [ -d "$SNAP/TITLE2" ] && [ ! -L "$SNAP" ] || { say "NOT STARTED, no $SNAP/TITLE2"; exit 1; }
         RENV="N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1"; mt=s ;;
  *) say "MODE is route or scene"; exit 1 ;;
esac
[ "${SW:0:8}" = f345db74 ] || { say "NOT STARTED, the shared normal is ${SW:0:8}, not f345db74"; exit 1; }
[ "$(md5sum < "$CB" | cut -d' ' -f1)" = "$CW" ] || { say "NOT STARTED, $CB is not ${CW:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$RUN" ] || { say "NOT STARTED, no $WORDS or $RUN"; exit 1; }
say "mode $MODE, play $PLAY s, order ${ORDER:-V Z V Z V Z}; candidate ${CW:0:8} (V: switch on, Z: BC5_DIRECT_VIEWS_GEN=0); runner $(md5sum < "$RUN" | cut -c1-8); kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
PADS=()
padon() { : > "$E/raw/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$E/raw/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
trap padoff EXIT
mkdir -p "$E/raw"
gpucount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
export R0436_BASE; R0436_BASE=$(gpucount)  # the name exp 0436's run0430f-0436.sh reads
say "GPU timeout/reset lines since boot at the chain's start: $R0436_BASE"
for arm in ${ORDER:-V Z V Z V Z}; do
  k=$((k + 1))
  case "$arm" in V) xw="" ; want_state=ON ;; Z) xw="BC5_DIRECT_VIEWS_GEN=0"; want_state=off ;; *) say "arm $arm: V or Z"; break ;; esac
  t=u437$mt$arm$k; while [ -e "$RAW/$t-start.txt" ] || [ -e "$RAW/$t-end.txt" ]; do t=${t}b; done
  [ -e "$E/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  [ -s "$W/BOX-LOCK" ] && { say "a BOX-LOCK line before $t that is not a run of ours: $(cat "$W/BOX-LOCK"): stop"; break; }
  [ "$(gpucount)" = "$R0436_BASE" ] || { say "GPU timeout/reset lines grew from $R0436_BASE to $(gpucount) before $t: stop"; break; }
  if [ "${DAY_OK:-0}" != 1 ] && [ "$(date +%H%M)" -ge 0700 ] && [ "$(date +%H%M)" -lt 1200 ]; then say "07:00-12:00 without DAY_OK=1: stop"; break; fi
  say "run $t, arm $arm (${xw:-switch on}), ${CW:0:8}"
  padon "$t"
  ( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done  # the binary that runs (R66)
    if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$E/raw/$t-exe.txt" 2>&1 &
  XP=$!
  # shellcheck disable=SC2086
  line=$(env $RENV N_FUSE=0 N_NOWD=1 P_BIN=$CB P_WANT=$CW P_WORDS=$WORDS bash "$RUN" "$t" h "$PLAY" $WAY2 $xw | grep "^$t ")
  padoff; wait "$XP" 2> /dev/null
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  G=$(sed -n 's/.*; G \([0-9]*\),.*/\1/p' "$RAW/$t-end.txt" 2> /dev/null)
  FPS=$(awk -v g="${G:-999999}" 'NF == 4 && $1 >= g + 10 {s += $3; f += $2; if ($4 > 50) a++; if ($4 > 100) b++} END {if (s > 0) printf "%.2f flips/s over %d s from G+10, %d s with a gap over 50 ms, %d over 100 ms", f / s, s, a, b; else printf "no fps lines after G+10"}' "$RAW/$t-fps.txt" 2> /dev/null)
  EXE=$(cat "$E/raw/$t-exe.txt" 2> /dev/null); PADN=$(grep -c . "$E/raw/$t-pad.txt" 2> /dev/null)
  VG=$(grep -a -m1 'tag vg437' "$RAW/$t-play.log" 2> /dev/null | cut -c1-160)
  J=$(sed -n 's/^journal \([^ ]*\) .*/\1/p' "$RAW/$t-journal.txt" 2> /dev/null)
  if [ -n "$J" ] && [ -f "$J" ]; then
    nice -n 19 grep -a "^frame profile: t\|^timing split\|tag vg437\|tag d432" "$J" | gzip -c > "$E/raw/$t-sync.txt.gz"
    VL=$(grep -a 'tag vg437' "$J" | tail -1 | cut -c1-240); NFP=$(grep -ac '^frame profile: t' "$J"); NTS=$(grep -ac '^timing split' "$J")
  else VL="no journal"; NFP=0; NTS=0; fi
  echo "$t $arm ${CLASS:-NONE} | $FPS | exe [$EXE] | pad keys $PADN | state [$VG] | last [$VL] | frame lines $NFP, split lines $NTS | $(printf '%s\n' "$line" | cut -c1-300)" >> "$OUT"
  say "$t: ${CLASS:-NONE}; $FPS; pad keys $PADN; $VL"
  case "$EXE" in *" md5 $CW") ;; *) say "$t ran another binary than ${CW:0:8} ($EXE): stop"; break ;; esac
  case "$VG" in *"BC5_DIRECT_VIEWS_GEN $want_state:"*) ;; *) say "$t: the vg437 state line is not '$want_state' ($VG): stop"; break ;; esac
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "class ${CLASS:-NONE}: stop (R55; the records are the result)"; break; }
  sleep 20
done
say "chain ended"
