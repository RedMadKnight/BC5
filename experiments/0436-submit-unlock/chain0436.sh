#!/usr/bin/env bash
# BC5 experiment 0436: shared normal (S) against the candidate's normal test build (C), alternating, one run at a time.
#   MODE=route  exp 0430's run0430f.sh as exp 0433's chain0433.sh calls it: slot 4 of exp 0425's named snapshot, the
#               maintainer's 14:50 fight record at G, then exp 0379's walk to G+$PLAY (default 1500); way 2's words named;
#               JobArenaFix off (N_ARENA=off); no fuse, no memory watchdog.
#   MODE=scene  exp 0432's run0432f.sh as scene0432.sh calls it: his 09:46 scene (the read-only snapshot
#               ~/bc5-data/saves/TITLE2-20261117-0946-play), slot 4, no input after the load, G+$PLAY (default 300).
# Both arms get the same words (way 2's five, BC5_DIRECT_TIMEOUT_PROBE=1 for a fault's record); the arm is the binary
# alone (the candidate's switch is on in its test build unless =0). RT on as the title's settings hold it.
# Per run, beside the runner: the emulator's /proc/<pid>/exe and its md5 once it starts (LESSONS R66: the binary that
# really ran), the pad's key events (R51: a key = the run is void as a measurement), and after the run flips/s and the
# seconds with a gap over 50 / 100 ms from G+10 s (the runner's fps lines). Each run takes and frees its own BOX-LOCK
# line (the runner). Stops: a class other than NO_CRASH (R55), a wrong binary, ~/bc5-work/exp0436/STOP (read before each
# run), an emulator that is not ours.
# usage (on the box, detached under the user manager, from ~/bc5-work/exp0436/kit):
#   MODE=route ORDER="S C S C S C" K0=0 bash chain0436.sh       (tags u436<r|s><S|C><k>)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0436; HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${MODE:?route or scene}; k=${K0:?the last run number}
SB=$W/kytyplus-build/src/kyty_emulator; CB=$E/normal/kyty_emulator
SW=$(md5sum < "$SB" | cut -d' ' -f1); CW=$(cat "$E/normal/binary.md5")
WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3 BC5_DIRECT_TIMEOUT_PROBE=1"
OUT=$E/chain-rows.txt
say() { echo "chain0436 $(date +%T): $*"; }
case "$MODE" in
  route) RUN=${ROUTE_RUN:-$W/exp0430/run0430f.sh};  # the original on a clean boot; ROUTE_RUN=$HERE/run0430f-0436.sh on a boot with old resets (ruling 2026-11-20)
  RAW=$W/exp0430/n/raw; PLAY=${PLAY:-1500}; RENV="N_ARENA=off N_WALK_AFTER=1 N_SLOT=4"; mt=r ;;
  scene) RUN=$W/exp0432/kit/run0432f.sh; RAW=$W/exp0432/n/raw; PLAY=${PLAY:-300}; SNAP=$HOME/bc5-data/saves/TITLE2-20261117-0946-play
         [ -d "$SNAP/TITLE2" ] && [ ! -L "$SNAP" ] || { say "NOT STARTED, no $SNAP/TITLE2"; exit 1; }
         RENV="N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1"; mt=s ;;
  *) say "MODE is route or scene"; exit 1 ;;
esac
[ "${SW:0:8}" = 99f2a567 ] || { say "NOT STARTED, the shared normal is ${SW:0:8}, not 99f2a567"; exit 1; }
[ "$(md5sum < "$CB" | cut -d' ' -f1)" = "$CW" ] || { say "NOT STARTED, $CB is not ${CW:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$RUN" ] || { say "NOT STARTED, no $WORDS or $RUN"; exit 1; }
say "mode $MODE, play $PLAY s, order ${ORDER:-S C S C S C}; shared ${SW:0:8}, candidate ${CW:0:8}; runner $(md5sum < "$RUN" | cut -c1-8); kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
PADS=()
padon() { : > "$E/raw/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$E/raw/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
trap padoff EXIT
mkdir -p "$E/raw"
# exp 0436 (the top session's ruling of 2026-11-20): this boot already has old amdgpu timeout/reset lines (exp 0434's first title
# faults, 11-19 14:06-14:14) and the box could not be rebooted; their count now is the baseline, the chain stops if it grows.
gpucount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:[0-9a-f]{2}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
export R0436_BASE; R0436_BASE=$(gpucount)
say "GPU timeout/reset lines since boot at the chain's start: $R0436_BASE (the baseline; the route runner refuses on any other count)"
for arm in ${ORDER:-S C S C S C}; do
  k=$((k + 1))
  case "$arm" in S) bin=$SB; want=$SW ;; C) bin=$CB; want=$CW ;; *) say "arm $arm: S or C"; break ;; esac
  t=u436$mt$arm$k; while [ -e "$RAW/$t-start.txt" ] || [ -e "$RAW/$t-end.txt" ]; do t=${t}b; done
  [ -e "$E/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  [ -s "$W/BOX-LOCK" ] && { say "a BOX-LOCK line before $t that is not a run of ours: $(cat "$W/BOX-LOCK"): stop"; break; }
  [ "$(gpucount)" = "$R0436_BASE" ] || { say "GPU timeout/reset lines grew from $R0436_BASE to $(gpucount) before $t: stop"; break; }
  [ "$(date +%H%M)" -ge 0700 ] && [ "$(date +%H%M)" -lt 1200 ] && { say "after 07:00: no new run without the top session (he may come to play): stop"; break; }
  say "run $t, arm $arm, ${want:0:8}"
  padon "$t"
  ( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done  # the binary that runs (R66)
    if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$E/raw/$t-exe.txt" 2>&1 &
  XP=$!
  # shellcheck disable=SC2086
  line=$(env $RENV N_FUSE=0 N_NOWD=1 P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$RUN" "$t" h "$PLAY" $WAY2 | grep "^$t ")
  padoff; wait "$XP" 2> /dev/null
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  G=$(sed -n 's/.*; G \([0-9]*\),.*/\1/p' "$RAW/$t-end.txt" 2> /dev/null)
  FPS=$(awk -v g="${G:-999999}" 'NF == 4 && $1 >= g + 10 {s += $3; f += $2; if ($4 > 50) a++; if ($4 > 100) b++} END {if (s > 0) printf "%.2f flips/s over %d s from G+10, %d s with a gap over 50 ms, %d over 100 ms", f / s, s, a, b; else printf "no fps lines after G+10"}' "$RAW/$t-fps.txt" 2> /dev/null)
  EXE=$(cat "$E/raw/$t-exe.txt" 2> /dev/null); PADN=$(grep -c . "$E/raw/$t-pad.txt" 2> /dev/null)
  SU=$(grep -a -m1 'tag su436' "$RAW/$t-play.log" 2> /dev/null | cut -c1-160)
  echo "$t $arm ${CLASS:-NONE} | $FPS | exe [$EXE] | pad keys $PADN | su436 [$SU] | $(printf '%s\n' "$line" | cut -c1-300)" >> "$OUT"
  say "$t: ${CLASS:-NONE}; $FPS; pad keys $PADN"
  case "$EXE" in *" md5 $want") ;; *) say "$t ran another binary than ${want:0:8} ($EXE): stop"; break ;; esac
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "class ${CLASS:-NONE}: stop (R55; the records are the result)"; break; }
  sleep 20
done
say "chain ended"
