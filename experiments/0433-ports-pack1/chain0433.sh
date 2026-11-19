#!/usr/bin/env bash
# BC5 exp 0433, step 3 (top's GO, 2026-11-19 00:1x): the fight route on the PRIVATE NORMAL ports-pack build, pack and control
# alternated. The control is the same binary with all 14 KYTY_BC5_P1_* words =0, so the pair isolates the pack.
# Each run: exp 0430's run0430f.sh as chain0430.sh calls it with CATCH=bake (slot 4, the 14:50 record's gameplay at G, then
# exp 0379's walk to G+1500 s; way 2's words named; BC5_DIRECT_TIMEOUT_PROBE=1 for a fault's record; JobArenaFix OFF in the
# run's private input.cfg, N_ARENA=off; RT on; no fuse, no memory watchdog; ulimit -c 0). Each run takes and frees its own
# BOX-LOCK line (run0430f.sh). run0430f.sh itself refuses to start after any GPU reset or ring timeout since boot.
# Stops: any class but NO_CRASH, a STOP file beside this script (read before each run), or an emulator that is not ours.
# usage (on the box, detached under the user manager, in ~/bc5-work/exp0433/kit): ORDER="P C P C P C" bash chain0433.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0433; R=$W/exp0430/n/raw; HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$E/normal/kyty_emulator; WANT=$(cat "$E/normal/binary.md5"); WORDS=$W/exp0413/n/words0413nz.txt
say() { echo "chain0433 $(date +%T): $*"; }
[ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$WANT" ] || { say "NOT STARTED, $BIN is not ${WANT:0:8}"; exit 1; }
[ -s "$WORDS" ] || { say "NOT STARTED, no $WORDS"; exit 1; }
OUT=$E/chain-rows.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3"
OFF=""
for w in EQ_WAKE_ALL NO_COND_REGISTRY FAULT_MASK SEMA_UAF AMPR_RESULT APR_FILE_ID COND_SIGNAL_ONE ALTSTACK PTHREAD_KEYS \
         PROT_RANGES FILE_UNBUFFERED AJM_GAPLESS AMPR_FILTER FATAL_TO_ERROR; do OFF="$OFF KYTY_BC5_P1_$w=0"; done
say "binary ${WANT:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); order ${ORDER:-P C P C P C}; A arm ${ARM_W:-none}; every run ${EXTRA_W:-nothing extra}"
np=0; nc=0; na=0
EXTRA=${EXTRA_W:-}  # words for every run of every arm (e.g. KYTY_BC5_P1_HITS=0)
for arm in ${ORDER:-P C P C P C}; do
  case "$arm" in P) np=$((np + 1)); t=${TAGP:-s433}f$np; AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1" ;;
                 C) nc=$((nc + 1)); t=${TAGP:-s433}c$nc; AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1$OFF" ;;
                 A) na=$((na + 1)); t=${TAGP:-s433}a$na; AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1 ${ARM_W:?ARM_W: the words of the A arm}" ;;
                 *) say "arm $arm: P, C or A"; break ;; esac
  AW="$AW $EXTRA"
  while [ -e "$R/$t-start.txt" ]; do t=${t}b; done
  [ -e "$HERE/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  say "run $t, arm $arm"
  # shellcheck disable=SC2086
  line=$(N_ARENA=off N_WALK_AFTER=1 N_SLOT=4 N_FUSE=0 N_NOWD=1 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS \
         bash "$W/exp0430/run0430f.sh" "$t" h 1500 $AW | grep "^$t ")
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  echo "$t $arm ${CLASS:-NONE} $(printf '%s\n' "$line" | cut -c1-400)" >> "$OUT"
  say "$t: ${CLASS:-NONE}"
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "class ${CLASS:-NONE}: stop (the records are the result)"; break; }
done
say "chain ended"
