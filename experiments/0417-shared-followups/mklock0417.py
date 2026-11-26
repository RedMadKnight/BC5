#!/usr/bin/env python3
"""BC5 experiment 0417: ONE lock line for a whole chain (the top session, 2026-11-13, after another session's claim
got between two steps of chk0417b.sh at 09:12: every step freed BOX-LOCK and the next one claimed it anew).

A chain now claims one line at its start ("... chain until about HH:MM") and exports it as CHAIN_LOCKLINE. Each step
script keeps its own atomic claim for use alone, and gets an inherited path: when BOX-LOCK holds exactly
CHAIN_LOCKLINE the step takes that line as its own, makes no claim, and its release does nothing; the chain frees
the line at its end or on a stop (chainlock0417.inc: chain_claim, chain_release, and a trap). A step called with
CHAIN_LOCKLINE set while the lock holds anything else refuses as before ("the box is locked").

  steps    start0413g.sh, start0413l.sh (exp 0413's integration directory) and run0413p.sh (this directory's)
           -> <out>/start0413g.sh, start0413l.sh, run0413p.sh
  build    a private-rebuild script made by mkkit0417b.py (p0417b.sh) -> <out>/<same name>: its claim() and release()
           get the same inherited path (it still prints "lock released", which the chains look for)
  inc      <out>/chainlock0417.inc
usage: mklock0417.py <repo root> <out dir> [<p-script to convert> ...]"""
import sys

root, out = sys.argv[1:3]
I = root + "/experiments/0413-np-session-v2-shared/integration/"
E = root + "/experiments/0417-shared-followups/"

CLAIM_HEAD = b'[ -e "$LOCK" ] || touch "$LOCK"\n'
CLAIM_TAIL = b'rm -f "$al" "$tl"\n'
PRE = (b'INHERIT=0  # exp 0417: a chain that holds ONE lock line for all its steps passes it in CHAIN_LOCKLINE\n'
       b'if [ -n "${CHAIN_LOCKLINE:-}" ] && [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK")" = "$CHAIN_LOCKLINE" ]; then INHERIT=1; LINE=$CHAIN_LOCKLINE\n'
       b'else\n')


def step(src, dst, release_old, release_new):
    s = open(src, "rb").read()
    assert b"\r" not in s and b"CHAIN_LOCKLINE" not in s
    assert s.count(CLAIM_HEAD) == 1 and s.count(CLAIM_TAIL) == 1
    a = s.index(CLAIM_HEAD)
    z = s.index(CLAIM_TAIL, a) + len(CLAIM_TAIL)
    block = s[a:z]
    assert block.count(b"\n") == 6 and b"the box is locked" in block and b"the claim failed" in block, block[:80]
    s = s[:a] + PRE + block + b"fi\n" + s[z:]
    assert s.count(release_old) == 1, release_old[:50]
    s = s.replace(release_old, release_new)
    open(dst, "wb").write(s)
    print(dst.rsplit("/", 1)[-1], "ok")


for name in ("start0413g.sh", "start0413l.sh"):
    step(I + name, out + "/" + name,
         b'release() { if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then',
         b'release() { [ "$INHERIT" = 1 ] && return 0; if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then')
step(E + "run0413p.sh", out + "/run0413p.sh",
     b'release() {\n  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then',
     b'release() {\n  [ "$INHERIT" = 1 ] && return 0  # exp 0417: the chain frees its own line\n  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then')

for p in sys.argv[3:]:
    s = open(p, "rb").read()
    assert b"\r" not in s and b"CHAIN_LOCKLINE" not in s
    old = b'    pgrep \'^kyty_emulator\' > /dev/null && stop "an emulator runs"\n    mkdir -p "$E" || stop "cannot make $E"\n'
    assert s.count(old) == 1
    s = s.replace(old, old +
                  b'    if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then  # exp 0417: the chain\'s one lock line\n'
                  b'        printf \'%s\\n\' "$CHAIN_LOCKLINE" > "$ID" || stop "cannot record the line"; INHERIT=1; echo "claimed: inherited from the chain: $CHAIN_LOCKLINE"; return 0\n'
                  b'    fi\n')
    old = b'release() {\n    if own; then'
    assert s.count(old) == 1
    s = s.replace(old, b'release() {\n    if [ "${INHERIT:-0}" = 1 ]; then rm -f "$ID"; echo "lock released (kept by the chain)"; return 0; fi\n    if own; then')
    name = p.replace("\\", "/").rsplit("/", 1)[-1]
    open(out + "/" + name, "wb").write(s)
    print(name, "ok")

open(out + "/chainlock0417.inc", "wb").write(b"""# BC5 exp 0417: one BOX-LOCK line for a whole chain (sourced by a chain script; made by mklock0417.py).
#   chain_claim "<what>" <minutes>   atomic claim (a hard link cannot replace an existing lock); exports CHAIN_LOCKLINE
#   chain_release                    removes exactly our line; also run by the EXIT trap this file sets
# The steps (start0413g.sh, start0413l.sh, run0413p.sh, the p-scripts) take the line over when they see it.
CHAIN_LOCK=$HOME/bc5-work/BOX-LOCK
chain_claim() {
    local t=$CHAIN_LOCK.chain-$$.new a=$CHAIN_LOCK.chain-$$.aside
    pgrep '^kyty_emulator' > /dev/null && { echo "chain: an emulator runs: not claimed"; return 1; }
    CHAIN_LOCKLINE="exp 0417 | chain: $1, until about $(date -d +"$2"min +%H:%M) | token $(date +%Y%m%d%H%M%S)$$ | $(date '+%F %T')"
    [ -e "$CHAIN_LOCK" ] || touch "$CHAIN_LOCK"
    [ -f "$CHAIN_LOCK" ] && [ ! -L "$CHAIN_LOCK" ] && [ ! -s "$CHAIN_LOCK" ] || { echo "chain: the box is locked: $(cat "$CHAIN_LOCK")"; return 1; }
    printf '%s\\n' "$CHAIN_LOCKLINE" > "$t" && mv -T "$CHAIN_LOCK" "$a" && ln "$t" "$CHAIN_LOCK" || { [ -e "$CHAIN_LOCK" ] || mv -T "$a" "$CHAIN_LOCK"; rm -f "$t"; echo "chain: the claim failed"; return 1; }
    if [ -s "$a" ]; then mv -fT "$a" "$CHAIN_LOCK"; rm -f "$t"; echo "chain: a foreign line arrived during the claim"; return 1; fi
    rm -f "$a" "$t"
    [ "$(cat "$CHAIN_LOCK")" = "$CHAIN_LOCKLINE" ] || { echo "chain: the lock does not read back as ours"; return 1; }
    export CHAIN_LOCKLINE
    printf '%s\\n' "exp 0417 | claimed: $CHAIN_LOCKLINE" >> "$HOME/bc5-work/BOX-QUEUE"
    trap chain_release EXIT
    echo "chain lock: $CHAIN_LOCKLINE"
}
chain_release() {
    [ -n "${CHAIN_LOCKLINE:-}" ] || return 0
    if [ -f "$CHAIN_LOCK" ] && grep -qxF -- "$CHAIN_LOCKLINE" "$CHAIN_LOCK"; then
        local t=$CHAIN_LOCK.chain-$$.rel; grep -vxF -- "$CHAIN_LOCKLINE" "$CHAIN_LOCK" > "$t"; mv -fT "$t" "$CHAIN_LOCK"
        printf '%s\\n' "exp 0417 | released: chain, $(date '+%F %T')" >> "$HOME/bc5-work/BOX-QUEUE"
        echo "chain lock released"
    else
        echo "chain: the lock no longer holds our line, left as it is: $(cat "$CHAIN_LOCK" 2> /dev/null)"
    fi
    CHAIN_LOCKLINE=""
}
""")
print("chainlock0417.inc ok")
