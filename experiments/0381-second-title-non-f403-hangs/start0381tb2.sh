#!/usr/bin/env bash
# BC5 exp 0381: test build 2's smoke start, RT on, the smoke launcher on a private copy reset from the named snapshot. The live saves
# are not read: the snapshot is the sample, and its sum in the start file says which one. The box-side cap stops it at 125 s: this is its first real test, so it fires before the laptop's backstop at 140 s.
# It runs under the series' exact lock line, which it never rewrites (lock0381tb2.inc). It writes the outcome line itself, after the launcher returned, and clears only that line.
# usage: ssh bc250 'bash -s' -- <tag> <token> < start0381tb2.sh
set -u
export LC_ALL=C
TAG=$1
TB2_TOKEN=${2:?token}
CAP=${TB2_CAP:-125}
ROOT=${TB2_ROOT:-$HOME}; W=$ROOT/bc5-work; S=$W/exp0379; E=$W/exp0381; TB=$E/tb2
LK=$E/in-tb2/experiments/0381-second-title-non-f403-hangs/lock0381tb2.inc
[ -f "$LK" ] || { echo "no lock helper at $LK: stop"; exit 7; }
. "$LK"
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
[ -x "$TB/bin/kyty_emulator" ] && [ -x "$TB/play-pkg-0381tb2s.sh" ] || { echo "no test binary or smoke launcher"; exit 1; }
[ -e "$TB/raw/$TAG-start.txt" ] && { echo "tag $TAG is used"; exit 6; }
# The sample's sum is in the C locale, as `export LC_ALL=C` above: sort -k2 orders these names differently under the box's default pl_PL.UTF-8.
SNAP_REL=bc5-work/exp0381/saves-sample
SNAP=$ROOT/$SNAP_REL
CAPS=$E/in-tb2/experiments/0381-second-title-non-f403-hangs/boxcap0381.sh
[ -f "$CAPS" ] || { echo "no box cap at $CAPS: stop"; exit 7; }
PC=$E/in-tb2/experiments/0381-second-title-non-f403-hangs/pathcheck0381tb2.inc
[ -f "$PC" ] || { echo "no path check at $PC: stop"; exit 7; }
. "$PC"
private() { BAD=$(tb2_private_all) || { echo "a private path is not itself: $BAD: stop, nothing written"; exit 9; }; }
private
grep -qx 'RayTracing.PPSA03671=on' "$E/input-rton.cfg" || { echo "the smoke config is not RT on"; exit 8; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
[ -d "$SNAP/PPSA03671" ] && tb2_private "$SNAP_REL" tree || { echo "no private snapshot at $SNAP: stop, snapshot0381tb2.sh makes it"; exit 5; }
SAMPLE=$(sum "$SNAP")
[ -d "$E/wd/_SaveData" ] || { echo "no private save directory: stop"; exit 5; }
private
tb2_own
rm -rf "$E/wd/_SaveData/PPSA03671" || { echo "the old copy was not removed: stop"; exit 5; }
tb2_own
cp -a "$SNAP/PPSA03671" "$E/wd/_SaveData/PPSA03671" || { echo "the save copy failed: stop"; exit 5; }
private
[ "$(sum "$E/wd/_SaveData")" = "$SAMPLE" ] || { echo "the save copy differs"; exit 5; }
tb2_own
cp "$S/in-D2.cmd" "$TB/in-$TAG.cmd" || { echo "the input script was not copied: stop"; exit 5; }
tb2_hook before-launch
tb2_own
tb2_queue "$TB2_LINE: smoke $TAG, cap $CAP s, RT on | $(date '+%F %T')"
finish() {
    tb2_queue_q "$TB2_LINE: smoke ended: $TAG, launcher returned, result read on the laptop | $(date '+%F %T')" || echo "TB2: no queue line: the lock is not ours"
    tb2_release
}
trap finish EXIT
tb2_hook at-launch
tb2_own
echo "$(date '+%F %T') $TAG start: binary $(md5sum < "$TB/bin/kyty_emulator" | cut -c1-8), launcher $(md5sum < "$TB/play-pkg-0381tb2s.sh" | cut -c1-8), sample $SAMPLE" > "$TB/raw/$TAG-start.txt"
setsid bash "$CAPS" /exp0381/tb2/bin/kyty_emulator "$CAP" "$TB/raw/$TAG-start.txt" < /dev/null > /dev/null 2>&1 &
distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD="$TB/in-$TAG.cmd" TB2_SERIES_LINE="$TB2_LINE" "$TB/play-pkg-0381tb2s.sh" < /dev/null > "$TB/raw/$TAG-launch.out" 2>&1
echo "launcher exit $?" >> "$TB/raw/$TAG-launch.out"
echo "$(date '+%F %T') launcher returned" >> "$TB/raw/$TAG-start.txt"
