#!/usr/bin/env bash
# BC5 exp 0413: the last private rebuild (patch 0001 P_NEW7: the guard on in code, BC5_R3_SUBMIT_EOP_EVENT out of the
# table) and the checks on exactly those binaries, in one unattended chain. Every step takes and releases BOX-LOCK by
# itself (p0413g.sh, sweep0413g.sh/start0413g.sh, run0413p.sh); the chain stops at a failed build.
#   f1  ASTRO BOT, plain defaults, 0 2 4 dummy variables, 30 s each
#   f2  ASTRO BOT, KYTY_BC5_SWITCH_DEFAULTS=0 alone, 60 s (the guard is in code: a pass with the guard's line expected)
#   f3  ASTRO BOT, KYTY_BC5_AMM_SETBUFFER_GUARD=0, 20 s (the control: the old crash expected where a4 is -1)
#   f4  ASTRO BOT, KYTY_BC5_NP_SESSION_V2=0 KYTY_BC5_FW_NET=0, 30 s (the run-time off side of step 22)
#   r3fin  the second title without the zero skip, 240 s after G, RT on
#   l4lean the lean binary's start, 120 s
# usage (on the box, detached): P_NEW7=<patch md5> final0413.sh
set -u
ulimit -c 0
export LC_ALL=C
E=$HOME/bc5-work/exp0413; N=$E/n; P=$E/p
: "${P_NEW7:?the patch md5}"
for _ in $(seq 1 120); do grep -q "chain done" "$N/chain-r.out" 2> /dev/null && break; sleep 10; done
grep -q "chain done" "$N/chain-r.out" || { echo "final: the earlier chain did not end"; exit 1; }
sleep 5
(cd "$P/kit" && P_NEW7=$P_NEW7 bash ./p0413g.sh) > "$P/p0413g.log" 2>&1
tail -3 "$P/p0413g.log"
grep -q "^lock released" "$P/p0413g.log" && grep -q " done; normal " "$P/p0413g.log" || { echo "final: the build did not end clean"; exit 1; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1)
echo "final binaries: normal $MN lean $ML"
cd "$N" || exit 1
export P_BIN=$BN P_WANT=$MN
bash ./sweep0413g.sh f1n 30 "0 2 4"
bash ./sweep0413g.sh f2n 60 "0" KYTY_BC5_SWITCH_DEFAULTS=0
bash ./sweep0413g.sh f3n 20 "0" KYTY_BC5_AMM_SETBUFFER_GUARD=0
bash ./sweep0413g.sh f4n 30 "0" KYTY_BC5_NP_SESSION_V2=0 KYTY_BC5_FW_NET=0
for t in f1n0 f2n0 f3n0 f4n0; do echo "$t: $(grep -a -h "SessionManager V2\|KYTY_BC5_AMM_SETBUFFER_GUARD o" "raw/$t-play.log" | sort | uniq -c | tr -s ' ' | tr '\n' ';')"; done
sleep 5
P_WORDS=$N/words0413nz.txt bash ./run0413p.sh r3fin nozeroskip 240
sleep 5
P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh l4lean lean 120
echo "final done $(date +%T)"
