#!/usr/bin/env bash
# BC5 exp 0393 from the laptop: one step, the build or one run (made from go0388.sh by mk0393.py). No retry of any step.
# usage: go0393.sh <build|tag> <deadline epoch>
# Exit: 0 a result, printed as its RESULT line; 2 stopped before or during the run, nothing further; 3 the result is
# unknown: the box finishes and frees its lock by itself, read <tag>-done.txt, or run the printed release.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SSH=ssh; SCP=scp; SHORT=60; XFER=120; POLL=15; RESULT_GRACE=-60
# Stand-ins load only from a d19-test- path.
case "${D19_RUN_FAKE:-}" in *d19-test-*) . "$D19_RUN_FAKE" ;; esac
TAG=${1:?tag}; DL=${2:?deadline epoch}
FILES="run0393.sh s6n0393.sh prestart0393.sh patch0393.py patch0277.py build0393.py pins0393.env"  # the private binary is pinned there
S=bc5-work/exp0393/s; RAW=bc5-work/exp0393/run/raw
LOG=$HERE/raw/$TAG-kernel-stream.txt
mkdir -p "$HERE/raw"
box() { timeout "$SHORT" "$SSH" -o ConnectTimeout=10 bc250 "$@"; }
over() { box "bash -s -- $*" < "$HERE/run0393.sh"; }
give_back() {
    echo "$TAG: giving the lock back"
    over release "$TOK" || echo "$TAG: release not confirmed, by hand: ssh bc250 'bash -s -- release $TOK' < run0393.sh"
}
out=$(over claim "$TAG" "$DL"); rc=$?
echo "$out"
TOK=$(printf '%s\n' "$out" | sed -n 's/^TOK=\([0-9][0-9]*\)$/\1/p')
if [ $rc != 0 ] || [ -z "$TOK" ]; then
    echo "$TAG: not claimed, or unknown: look at BOX-LOCK before anything else"
    exit 2
fi
(cd "$HERE" && sha256sum $FILES | sed 's/ \*/  /') > "$HERE/raw/$TAG-sent.sha256"
# shellcheck disable=SC2086
if ! (cd "$HERE" && timeout "$XFER" "$SCP" -q $FILES "bc250:$S/"); then echo "$TAG: the send failed"; give_back; exit 2; fi
if ! box "cd ~/$S && sha256sum $FILES" | sed 's/ \*/  /' | cmp - "$HERE/raw/$TAG-sent.sha256"; then echo "$TAG: the sent files differ"; give_back; exit 2; fi
# The whole run, not the short ssh cap. The box's dmesg gates decide; this copy is for a machine-down. It ends with the lock.
L=$((DL - $(date +%s)))
timeout "$L" "$SSH" -o ConnectTimeout=10 bc250 "bash ~/$S/run0393.sh stream $TOK $L" > "$LOG" 2>&1 &
K=$!
trap 'kill "$K" 2> /dev/null' EXIT
if ! box "bash ~/$S/run0393.sh start $TOK $TAG $DL" > /dev/null; then echo "$TAG: start not confirmed"; give_back; exit 2; fi
done=""; lost=0
while [ "$(date +%s)" -lt $((DL + RESULT_GRACE)) ]; do
    sleep "$POLL"
    if r=$(box "cat ~/$RAW/$TAG-done.txt 2> /dev/null; true"); then
        [ -z "$r" ] || { done=$r; break; }
    else
        lost=$((lost + 1))
    fi
done
[ "$lost" = 0 ] || echo "$TAG: $lost polls had no answer"
if [ -z "$done" ]; then
    echo "$TAG: UNKNOWN: no result by the deadline. The box ends the run itself under its limit."
    echo "read: ssh bc250 cat ~/$RAW/$TAG-done.txt; recovery: ssh bc250 'bash -s -- release $TOK' < run0393.sh"
    exit 3
fi
echo "$done"
res=$(box "cat ~/$RAW/$TAG-result.txt 2> /dev/null; true")
[ -n "$res" ] || { echo "$TAG: no result file"; exit 2; }
echo "$res"
if grep -qi amdgpu "$LOG"; then echo "$TAG: an amdgpu line in the kernel stream"; exit 2; fi
[ "$(printf '%s\n' "$done" | tail -1)" = "lock released" ] || { echo "$TAG: the lock was not released cleanly"; exit 2; }
l=$(box "cat ~/bc5-work/BOX-LOCK 2> /dev/null; true") || { echo "$TAG: the lock could not be read back"; exit 2; }
case "$l" in *"token $TOK "*) echo "$TAG: our line is still in the lock"; exit 2 ;; esac
exit 0
