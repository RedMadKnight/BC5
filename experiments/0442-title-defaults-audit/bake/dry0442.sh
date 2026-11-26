#!/usr/bin/env bash
# BC5 exp 0442 (tag bake442): swap0442.sh's dry run on copies of the tree and of the backend source (CPU only, no lock
# line, no build, nothing shared written). Prints PATCH_NEW and leaves the new patch in ~/bc5-work/exp0442/dry/.
# usage (on the box, in the kit directory): bash dry0442.sh
set -u
export LC_ALL=C
D=$HOME/bc5-work/exp0442/dry; HERE=$(cd "$(dirname "$0")" && pwd)
[ -s "$HOME/bc5-work/BOX-LOCK" ] && { echo "dry0442: BOX-LOCK holds a line: not run"; exit 1; }
rm -rf "$D"; mkdir -p "$D" || exit 1
nice -n 19 cp -a "$HOME/src/KytyPlus" "$D/kyty" && nice -n 19 cp -a "$HOME/bc5-work/d19/export/backend" "$D/backend" || { echo "dry0442: copy failed"; exit 1; }
DRY=1 INT_K=$D/kyty INT_B=$D/backend X=$D/x bash "$HERE/swap0442.sh"
r=$?
[ -s "$D/0001-new0442.dry.patch" ] && echo "dry0442: new patch $(md5sum < "$D/0001-new0442.dry.patch" | cut -c1-8), $(wc -c < "$D/0001-new0442.dry.patch") bytes"
rm -rf "$D/kyty" "$D/backend"
exit $r
