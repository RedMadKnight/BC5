#!/usr/bin/env bash
# BC5 exp 0430: fight + walk runs on the private catcher build until a GPU hang is caught (the top session's GO for the whole
# 0430 chain, 2026-11-16). Way 2 on (the title rows, named here too), JobArenaFix OFF in each run's private input.cfg
# (N_ARENA=off), RT on, no fuse and no memory watchdog (N_FUSE=0 N_NOWD=1: diagnostics only), ulimit -c 0 (the launcher).
# Each run: run0430f.sh, slot 4, the 14:50 record's gameplay at G, then exp 0379's walk to G+1500 s; each run takes and frees
# its own BOX-LOCK line. Catchers on: BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=1100 BC5_DIRECT_TIMEOUT_PROBE=1.
# Stops: any class but NO_CRASH (KERNEL = a hang caught: the records are the result), a second NOT_ROUTED, MAX runs,
# a STOP file beside this script (read before each run), or a running emulator that is not ours.
# usage (on the box, detached, in ~/bc5-work/exp0430): MAX=<n> bash chain0430.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0430; N=$E/n; R=$N/raw; HERE=$(cd "$(dirname "$0")" && pwd)
BIN=${CHAIN_BIN:-$E/kyty_emulator}; WORDS=$W/exp0413/n/words0413nz.txt; MAX=${MAX:-6}  # CHAIN_BIN: a control binary (its md5 is taken as is)
say() { echo "chain0430 $(date +%T): $*"; }
if [ -n "${CHAIN_BIN:-}" ]; then [ -x "$BIN" ] || { say "NOT STARTED, no $BIN"; exit 1; }; WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
else
[ -x "$BIN" ] && [ -s "$E/binary.md5" ] || { say "NOT STARTED, no private binary"; exit 1; }
WANT=$(cat "$E/binary.md5"); [ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$WANT" ] || { say "NOT STARTED, the binary is not ${WANT:0:8}"; exit 1; }
fi
[ -s "$WORDS" ] || { say "NOT STARTED, no $WORDS"; exit 1; }
mkdir -p "$R" || exit 1
OUT=$N/chain-rows.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3"
# exp 0430 build 5: CATCH=0 runs the fix alone (F3, F2 as its fallback, the timeout probe; G and every catcher off) for flips/s;
# otherwise every catcher, G with a dump at t 600 s, and the fix
if [ "${CATCH:-1}" = bake ]; then AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1"  # 2026-11-18 evening: the hang fix built in (no switch); the probe for a fault's record
elif [ "${CATCH:-1}" = swap ]; then AW="$WAY2 BC5_DIRECT_XQ_PENDING=1 BC5_DIRECT_XQ_ACQUIRE=1 BC5_DIRECT_TIMEOUT_PROBE=1"  # build 6: the shared form (MODE=swap build)
elif [ "${CATCH:-1}" = 0 ]; then AW="$WAY2 BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_G=0 BC5_DIRECT_TIMEOUT_PROBE=1"
else AW="$WAY2 BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=${WAVES_MS:-900} BC5_0430_SNAP=1 BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_F4=${F4:-1} BC5_0430_G=1 BC5_0430_G_AT=300 BC5_0430_TABLES=1 BC5_0430_TABLE_PGMS=909973900,909973b00,909973d00,909973f00,909974400,909977100,90997a500 BC5_DIRECT_TIMEOUT_PROBE=1"; fi
AW="$AW ${EXTRA_W:-}"  # 2026-11-17: more words for one arm (ab0430.sh FWORDS: the F7 arm with F6/F6b off)
say "binary ${WANT:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id); max $MAX runs"
NR=0; k=${K0:-0}; MAX=$((k + MAX))  # K0: the first run is number K0+1 (a chain restarted between runs)
while [ "$k" -lt "$MAX" ]; do
  k=$((k + 1))
  t=${TAGP:-h430R}$k
  while [ -e "$R/$t-start.txt" ]; do t=${t}b; done
  [ -e "$HERE/STOP" ] && { say "STOP file before $t"; break; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; break; }
  say "run $t"
  # shellcheck disable=SC2086
  line=$(N_ARENA=off N_WALK_AFTER=1 N_SLOT=4 N_FUSE=0 N_NOWD=1 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0430f.sh" "$t" h 1500 $AW | grep "^$t ")
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  echo "$t ${CLASS:-NONE} $(printf '%s\n' "$line" | cut -c1-400)" >> "$OUT"
  say "$t: ${CLASS:-NONE}"
  ls "$(ls -td ~/bc5-data/captures/play-*/gc 2> /dev/null | head -1)" 2> /dev/null | grep -E 'dj0430|waves0430|snap0430|tab0430|g0430' | sed "s/^/$t catcher file: /" >> "$OUT"
  case "${CLASS:-NONE}" in
    NO_CRASH) ;;
    NOT_ROUTED) NR=$((NR + 1)); [ "$NR" -ge 2 ] && { say "a second NOT_ROUTED: stop"; break; } ;;
    *) say "class ${CLASS:-NONE}: stop (the records are the result)"; break ;;
  esac
done
say "chain ended after $k run(s)"
