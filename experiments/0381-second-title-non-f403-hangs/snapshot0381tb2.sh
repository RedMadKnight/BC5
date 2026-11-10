#!/usr/bin/env bash
# BC5 exp 0381: test build 2's named save snapshot: one private copy of the live saves for repeatable tests, made once. Each start resets
# its private copy from it. It reads the live saves and writes only exp0381/saves-sample. It needs the series' exact lock line and no
# emulator. The saves need no protection, so nothing is compared with them: the sum printed here identifies the sample. A failed copy
# is removed and the snapshot appears only whole. Undo: recover0381tb2.sh renames it aside.
# usage: ssh bc250 'bash -s' -- <token> < snapshot0381tb2.sh
set -u
export LC_ALL=C
TB2_TOKEN=${1:?token}
ROOT=${TB2_ROOT:-$HOME}; W=$ROOT/bc5-work; E=$W/exp0381
SNAP_REL=bc5-work/exp0381/saves-sample
SNAP=$ROOT/$SNAP_REL
TMP=$SNAP.tmp
LK=$E/in-tb2/experiments/0381-second-title-non-f403-hangs/lock0381tb2.inc
[ -f "$LK" ] || { echo "no lock helper at $LK: stop"; exit 7; }
. "$LK"
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
PC=$E/in-tb2/experiments/0381-second-title-non-f403-hangs/pathcheck0381tb2.inc
[ -f "$PC" ] || { echo "no path check at $PC: stop"; exit 7; }
. "$PC"
private() { tb2_private bc5-work/exp0381 dir && tb2_private "$SNAP_REL" tree && tb2_private "$SNAP_REL.tmp" tree || { echo "the snapshot's path is not itself: stop, nothing written"; exit 9; }; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
private
if [ -e "$SNAP" ]; then
    echo "snapshot already there: $SNAP, sample $(sum "$SNAP")"; exit 0
fi
[ ! -e "$TMP" ] || { echo "$TMP is there: stop and ask"; exit 5; }
tb2_hook before-snapshot
tb2_own
mkdir "$TMP" || { echo "no directory: stop"; exit 5; }
tb2_own
cp -a "$W/_SaveData/PPSA03671" "$TMP/PPSA03671" || { rm -rf "$TMP"; echo "the copy failed: stop"; exit 5; }
private
tb2_own
mv "$TMP" "$SNAP" || { rm -rf "$TMP"; echo "the rename failed: stop"; exit 5; }
echo "snapshot made: $SNAP, sample $(sum "$SNAP"), $(find "$SNAP" -type f | wc -l) files, $(du -sh "$SNAP" | cut -f1)"
