#!/usr/bin/env bash
# BC5 exp 0422: the whole box round under ONE BOX-LOCK line: the top session's waiting line (its NAS install test,
# not started; the top's GO says to take it out when we start) is removed only if it is the lock's whole content,
# then our line is claimed, then int0422.sh (swap + build), then chk0422.sh (the runs). int0422.sh undoes itself
# on any failure; the runs do not undo the swap (that is the top's decision on the report).
# usage (on the box, detached, in ~/bc5-work/exp0422): PIN_OLD=<8 hex> bash chain0422.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; HERE=$(cd "$(dirname "$0")" && pwd); LOCK=$W/BOX-LOCK
: "${PIN_OLD:?}"
TOPLINE="top 2026-11-15 16:03:58: NAS install test next (uninstall + install of PPSA03671 from the NAS pkg), waiting for the maintainer to mount the NAS"
pgrep '^kyty_emulator' > /dev/null && { echo "chain0422 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
if [ -f "$LOCK" ] && [ "$(cat "$LOCK")" = "$TOPLINE" ]; then
    t=$LOCK.0422-$$.rel; : > "$t" && mv -fT "$t" "$LOCK" && echo "the top's waiting line taken out ($(date +%T))"
    printf '%s\n' "exp 0422 | the top's waiting NAS line taken out (its GO) | $(date '+%F %T')" >> "$W/BOX-QUEUE"
fi
. "$N/chainlock0417.inc"
chain_claim "exp 0422: the save fix fixed on, shared swap (normal+lean) and its checks (ASTRO BOT x6, the second title walk normal + lean)" 50 || { echo "chain0422 ended $(date +%T): NOT STARTED"; exit 1; }
echo "== $(date +%T) int0422"
PIN_OLD=$PIN_OLD bash "$HERE/int0422.sh" || { echo "chain0422 ended $(date +%T): the swap FAILED (int0422 undid it)"; exit 1; }
echo "== $(date +%T) chk0422"
bash "$HERE/chk0422.sh"
echo "chain0422 ended $(date +%T)"
