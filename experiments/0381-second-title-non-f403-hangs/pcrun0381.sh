#!/usr/bin/env bash
# BC5 exp 0381 (PORT-CHAIN): from the laptop: guard and claim, then the check. Each step runs only if the one before
# passed, and this script writes no outcome line: pcbox0381.sh does, and only after a claim.
# usage (in a checkout, the tree to check given): pcrun0381.sh <commit>
# The laptop's side ends after 15 minutes (PC_TIMEOUT); after that, or a dropped ssh, read the box's state and settle only
# this check's own lock.
# PC_REMOTE: the command that runs a shell line on the box (default: ssh bc250); the dry run sets a local stand-in.
set -u
COMMIT=${1:?a commit}; HERE=$(cd "$(dirname "$0")" && pwd)
REMOTE=${PC_REMOTE:-ssh bc250}
# The tree goes across first, so that a failed extract leaves no lock behind; the guard is read again before the claim.
CLAIM='W=$HOME/bc5-work; T="top exp 0381 | PORT-CHAIN"
guard() { pgrep "^kyty_emulator" > /dev/null && { echo "GUARD: an emulator runs; lock: $(cat $W/BOX-LOCK)"; exit 3; }; [ -s $W/BOX-LOCK ] && { echo "GUARD: lock: $(cat $W/BOX-LOCK)"; exit 4; }; return 0; }
guard
[ -e $W/exp0381/pc ] && mv $W/exp0381/pc $W/exp0381/pc-before-$(date +%Y%m%d-%H%M%S)
mkdir -p $W/exp0381/pc && tar -xf - -C $W/exp0381/pc || { echo "extract failed"; exit 5; }
guard
echo "$T CPU check (clang, Catch2, selftest without submit, no GPU) | $(date "+%F %T")" > $W/BOX-LOCK
echo "$T claim | $(date "+%F %T")" >> $W/BOX-QUEUE
echo claimed'
TOP=$(git -C "$HERE" rev-parse --show-toplevel)
X=$(mktemp -d); trap 'rm -rf "$X"' EXIT
git -C "$TOP" archive "$COMMIT" backend | tar -xf - -C "$X" || { echo "no such tree: nothing run, nothing recorded"; exit 3; }
SUM=${PC_EXPECT:-$(cd "$X" && find backend -type f -exec md5sum {} + | sed 's/ \*/  /' | LC_ALL=C sort -k2 | md5sum | cut -c1-16)}
echo "commit $(git -C "$TOP" rev-parse "$COMMIT"), backend tree $(git -C "$TOP" rev-parse "$COMMIT:backend"), source manifest $SUM"
git -C "$TOP" archive "$COMMIT" backend | $REMOTE "$CLAIM"
rcs=("${PIPESTATUS[@]}")
[ "${rcs[0]}" = 0 ] && [ "${rcs[1]}" = 0 ] || { echo "not claimed: nothing run, nothing recorded"; exit 3; }
timeout ${PC_TIMEOUT:-900} $REMOTE "bash -s -- $SUM" < "$HERE/pcbox0381.sh"
rc=$?
echo "check rc $rc"
exit $rc
