# exp 0381 test build 2: who owns BOX-LOCK. One exact line, with one token, from the claim to the release: never rewritten, and a line next to it means it is not ours.
# The claim is D19's (d19box.sh, archive-d19.sh, reviewed in REVIEW-PORTS-21): the line appears by a hard link, which cannot replace an existing lock. An empty lock is free to claim, and is never ownership.
# Needs W and TB2_TOKEN. A lost lock stops the script and is left as it is; only our exact line is ever cleared.
TB2_LOCK=$W/BOX-LOCK; TB2_QUEUE=$W/BOX-QUEUE; TB2_HELD=0
TB2_LINE="top exp 0381 | test build 2 | token $TB2_TOKEN"
# Stand-ins load only from a tb2-test- path.
tb2_hook() { case "${TB2_FAKE:-}" in *tb2-test-*) . "$TB2_FAKE" "$1" ;; esac; }
tb2_hook load
tb2_own_q() { [ -f "$TB2_LOCK" ] && [ ! -L "$TB2_LOCK" ] && [ "$(cat "$TB2_LOCK" 2> /dev/null)" = "$TB2_LINE" ]; }
tb2_own() { tb2_own_q || { echo "TB2 STOP: the lock is not ours: $(cat "$TB2_LOCK" 2> /dev/null)"; exit 4; }; }
tb2_queue_q() { tb2_own_q && { printf '%s\n' "$1" >> "$TB2_QUEUE"; } 2> /dev/null && grep -qxF -- "$1" "$TB2_QUEUE" 2> /dev/null; }
tb2_queue() { tb2_queue_q "$1" || { echo "TB2 STOP: the queue line was not written: $1"; exit 4; }; }
tb2_release() {
    tb2_hook before-release
    if tb2_own_q; then : > "$TB2_LOCK" || echo "TB2: the lock could not be released"
    else echo "TB2: the lock is not ours, left as it is: $(cat "$TB2_LOCK" 2> /dev/null)"; fi
}
tb2_claim_inner() {
    local t=$1 a=$2
    printf '%s\n' "$TB2_LINE" > "$t" 2> /dev/null || { WHY="cannot write $t"; return 1; }
    if [ -e "$TB2_LOCK" ] || [ -L "$TB2_LOCK" ]; then
        if [ -L "$TB2_LOCK" ] || [ ! -f "$TB2_LOCK" ]; then WHY="$TB2_LOCK is not a plain file"; return 1; fi
        if [ -s "$TB2_LOCK" ]; then WHY="foreign lock: $(cat "$TB2_LOCK")"; return 1; fi
        mv -T "$TB2_LOCK" "$a" 2> /dev/null || { WHY="the lock moved under us"; return 1; }
        tb2_hook after-aside
    fi
    if ! ln "$t" "$TB2_LOCK" 2> /dev/null; then
        WHY="lost the claim to: $(cat "$TB2_LOCK" 2> /dev/null)"
        [ -s "$a" ] || rm -f "$a"
        return 1
    fi
    if [ -s "$a" ]; then
        WHY="a foreign lock arrived during the claim: $(cat "$a")"
        mv -fT "$a" "$TB2_LOCK" 2> /dev/null || WHY="$WHY; restore it from $a"
        return 1
    fi
    rm -f "$a"
    [ "$(cat "$TB2_LOCK" 2> /dev/null)" = "$TB2_LINE" ] || { WHY="the lock does not read back as ours"; return 1; }
}
tb2_claim() {
    local c=$TB2_LOCK.tb2-claim t=$TB2_LOCK.tb2-$$.new a=$TB2_LOCK.tb2-$$.aside WHY=""
    mkdir "$c" 2> /dev/null || { echo "TB2 STOP: another claim runs, or $c was left behind"; exit 4; }
    if ! tb2_claim_inner "$t" "$a"; then
        rm -f "$t"; rmdir "$c"
        echo "TB2 STOP: $WHY"; exit 4
    fi
    TB2_HELD=1
    rm -f "$t"
    rmdir "$c" || { echo "TB2 STOP: cannot remove $c"; exit 4; }
}
# Set as the EXIT trap of a step that claims: it gives back only what that step still holds. A step that hands the lock on sets TB2_HELD=0.
tb2_held_release() { [ "$TB2_HELD" = 1 ] || return 0; TB2_HELD=0; tb2_release; }
# end of exp 0381 test build 2's lock
