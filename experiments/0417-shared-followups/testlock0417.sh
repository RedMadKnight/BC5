#!/usr/bin/env bash
# BC5 exp 0417: a stand-in test of the one-lock-per-chain change (mklock0417.py), laptop only, no box.
# It cuts the claim block and release() out of each converted step script and runs them, with stand-in variables,
# against a lock file in a temporary HOME. Cases per step script:
#   alone      empty lock, no CHAIN_LOCKLINE: the step claims its own line; release empties the lock
#   chain      the chain holds its line: the step inherits it (no new claim); its release leaves the lock as it is
#   foreign    CHAIN_LOCKLINE is set but the lock holds another line: the step refuses, the lock is untouched
# and for the chain's own functions: claim on an empty lock, refusal on a foreign lock, release, and the EXIT trap.
# usage: testlock0417.sh <directory with the converted scripts and chainlock0417.inc>
set -u
D=$(cd "${1:?the directory}" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/lock0417-XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
export HOME=$T; mkdir -p "$T/bc5-work"; LOCKF=$T/bc5-work/BOX-LOCK
fails=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
type pgrep > /dev/null 2>&1 || pgrep() { return 1; }   # no emulator on the laptop
export -f pgrep 2> /dev/null
cut_step() {  # script -> a runnable fragment: stand-in variables, the claim block, release(), then "$@"
    local f=$1 a z r
    a=$(grep -n '^INHERIT=0' "$f" | cut -d: -f1); z=$(grep -n '^fi$' "$f" | awk -F: -v a="$a" '$1 > a {print $1; exit}')
    r=$(grep -n '^release() {' "$f" | cut -d: -f1)
    { echo 'W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; TAG=t1; T=123; LINE="exp 0413 | private step $TAG, token $T"'
      sed -n "${a},${z}p" "$f"
      if grep -q '^release() {$' "$f"; then sed -n "${r},/^}/p" "$f"; else sed -n "${r}p" "$f"; fi
      echo 'echo "INHERIT=$INHERIT LOCK=[$(cat "$LOCK")]"; release; echo "AFTER=[$(cat "$LOCK")]"'; } > "$T/frag.sh"
}
for s in start0413g.sh start0413l.sh run0413p.sh; do
    cut_step "$D/$s"
    : > "$LOCKF"; o=$(env -u CHAIN_LOCKLINE bash "$T/frag.sh" 2>&1)
    case "$o" in *"INHERIT=0 LOCK=[exp 0413 | private step t1, token 123]"*"AFTER=[]"*) ok "$s alone: own claim, released" ;; *) bad "$s alone: $o" ;; esac
    echo "CHAIN LINE" > "$LOCKF"; o=$(CHAIN_LOCKLINE="CHAIN LINE" bash "$T/frag.sh" 2>&1)
    case "$o" in *"INHERIT=1 LOCK=[CHAIN LINE]"*"AFTER=[CHAIN LINE]"*) ok "$s in a chain: inherited, not released" ;; *) bad "$s chain: $o" ;; esac
    echo "SOMEONE ELSE" > "$LOCKF"; o=$(CHAIN_LOCKLINE="CHAIN LINE" bash "$T/frag.sh" 2>&1); rc=$?
    case "$rc:$o" in 1:*"the box is locked: SOMEONE ELSE"*) [ "$(cat "$LOCKF")" = "SOMEONE ELSE" ] && ok "$s under a foreign lock: refused, lock untouched" || bad "$s foreign: lock changed" ;; *) bad "$s foreign: rc $rc $o" ;; esac
    : > "$LOCKF"; o=$(CHAIN_LOCKLINE="CHAIN LINE" bash "$T/frag.sh" 2>&1)
    case "$o" in *"INHERIT=0"*"AFTER=[]"*) ok "$s with a stale CHAIN_LOCKLINE and an empty lock: own claim" ;; *) bad "$s stale: $o" ;; esac
done
# the chain's own functions
: > "$LOCKF"
o=$(bash -c ". '$D/chainlock0417.inc'; pgrep() { return 1; }; chain_claim 'a test' 50 || exit 9; echo \"HELD=[\$(cat \$CHAIN_LOCK)]\"; [ \"\$(cat \$CHAIN_LOCK)\" = \"\$CHAIN_LOCKLINE\" ] && echo SAME" 2>&1)
case "$o" in *"chain lock: exp 0417 | chain: a test, until about "*"SAME"*"chain lock released"*) [ ! -s "$LOCKF" ] && ok "chain: claimed, read back, freed by the EXIT trap" || bad "chain: lock not empty after exit" ;; *) bad "chain claim: $o" ;; esac
[ "$(grep -c 'claimed: exp 0417 | chain' "$T/bc5-work/BOX-QUEUE")" = 1 ] && [ "$(grep -c 'released: chain' "$T/bc5-work/BOX-QUEUE")" = 1 ] && ok "chain: the queue has the claim and the release" || bad "chain: queue lines"
echo "SOMEONE ELSE" > "$LOCKF"
o=$(bash -c ". '$D/chainlock0417.inc'; pgrep() { return 1; }; chain_claim 'a test' 50; echo rc=\$?" 2>&1)
case "$o" in *"chain: the box is locked: SOMEONE ELSE"*"rc=1"*) [ "$(cat "$LOCKF")" = "SOMEONE ELSE" ] && ok "chain under a foreign lock: refused, lock untouched" || bad "chain foreign: lock changed" ;; *) bad "chain foreign: $o" ;; esac
: > "$LOCKF"
o=$(bash -c ". '$D/chainlock0417.inc'; pgrep() { return 1; }; chain_claim 'a test' 50 > /dev/null; echo 'INTRUDER' > \$CHAIN_LOCK; chain_release" 2>&1)
case "$o" in *"the lock no longer holds our line, left as it is: INTRUDER"*) [ "$(cat "$LOCKF")" = "INTRUDER" ] && ok "chain release when the line is gone: nothing removed" || bad "chain release: lock changed" ;; *) bad "chain release: $o" ;; esac
: > "$LOCKF"
o=$(bash -c ". '$D/chainlock0417.inc'; pgrep() { return 0; }; chain_claim 'a test' 50; echo rc=\$?" 2>&1)
case "$o" in *"an emulator runs: not claimed"*"rc=1"*) [ ! -s "$LOCKF" ] && ok "chain with an emulator running: not claimed" || bad "chain emulator: lock written" ;; *) bad "chain emulator: $o" ;; esac
echo "testlock0417: $fails failed"
[ "$fails" = 0 ]
