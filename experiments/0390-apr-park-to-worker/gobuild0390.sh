#!/usr/bin/env bash
# BC5 exp 0390 from the laptop: the private build, in a slot from the top session. No retry of any step.
# usage: gobuild0390.sh [minutes the lock line announces]
# Exit: 0 built, the binary's md5 is in pins0390.env; 2 stopped, the lock given back or never taken; 3 unknown: the box
# may still be working, so nothing is released: read BOX-LOCK and the printed recovery.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SSH=ssh; SCP=scp; SHORT=60; XFER=120; BUILD=600
# Stand-ins load only from a d19-test- path.
case "${D19_RUN_FAKE:-}" in *d19-test-*) . "$D19_RUN_FAKE" ;; esac
MIN=${1:-15}
FILES="box0390.sh build0390.py patch0390.py units0390.sha256 patched0390.sha256"
D=bc5-work/exp0390/s
OUT=$HERE/raw/build-box.txt
mkdir -p "$HERE/raw"
box() { timeout "$SHORT" "$SSH" -o ConnectTimeout=10 bc250 "$@"; }
over() { box "bash -s -- $*" < "$HERE/box0390.sh"; }
give_back() {
    echo "gobuild: giving the lock back"
    over release || echo "gobuild: release not confirmed, by hand: ssh bc250 'bash -s -- release' < box0390.sh"
}
out=$(over claim "'private build'" "$MIN"); rc=$?  # over() flattens its words, so the box's shell must get these quotes
echo "$out"
[ "$rc" = 0 ] || { echo "gobuild: not claimed, or unknown: look at BOX-LOCK before anything else"; exit 2; }
(cd "$HERE" && sha256sum $FILES | sed 's/ \*/  /') > "$HERE/raw/build-sent.sha256"
# shellcheck disable=SC2086
if ! (cd "$HERE" && timeout "$XFER" "$SCP" -q $FILES "bc250:$D/"); then echo "gobuild: the send failed"; give_back; exit 2; fi
if ! box "cd ~/$D && sha256sum $FILES" | sed 's/ \*/  /' | cmp - "$HERE/raw/build-sent.sha256"; then echo "gobuild: the sent files differ"; give_back; exit 2; fi
timeout "$BUILD" "$SSH" -o ConnectTimeout=10 bc250 "bash ~/$D/box0390.sh build" > "$OUT" 2>&1; rc=$?
cat "$OUT"
case "$rc" in
    0) ;;
    1) echo "gobuild: the build stopped"; give_back; exit 2 ;;
    *)  # Our transport ended; the box may still be compiling, so its lock stays until someone has looked.
        echo "gobuild: UNKNOWN, rc $rc. Read ~/bc5-work/exp0390/raw/build.out, BOX-LOCK and pgrep cc1plus; recovery: ssh bc250 'bash -s -- release' < box0390.sh"
        exit 3 ;;
esac
md5=$(sed -n 's/^private binary \([0-9a-f]\{32\}\), .*/\1/p' "$OUT")
[ -n "$md5" ] || { echo "gobuild: no binary line in the output"; give_back; exit 2; }
sed -i "s/^NORMAL=.*/NORMAL=$md5/" "$HERE/pins0390.env"
over release || { echo "gobuild: the release was not confirmed: the build stands, look at BOX-LOCK"; exit 3; }
echo "gobuild: private binary $md5, pinned in pins0390.env"
