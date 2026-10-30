#!/usr/bin/env bash
# BC5 exp 0381: the test build's smoke start: 120 s, RT on, the smoke launcher on a fresh private copy of the live saves
# (never the live saves), with the box-side cap's first real use. The stop comes from the laptop first (tbrun0381.sh).
# usage: ssh bc250 'bash -s' -- <tag> < start0381tb.sh
set -u
TAG=$1
W=$HOME/bc5-work; S=$W/exp0379; E=$W/exp0381; TB=$E/tb
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
[ -s "$W/BOX-LOCK" ] && ! grep -q '^top exp 0381 |' "$W/BOX-LOCK" && { echo "GUARD: BOX-LOCK: $(cat "$W/BOX-LOCK")"; exit 4; }
[ -x "$TB/bin/kyty_emulator" ] && [ -x "$TB/play-pkg-0381tbs.sh" ] || { echo "no test binary or smoke launcher"; exit 1; }
[ -e "$TB/raw/$TAG-start.txt" ] && { echo "tag $TAG is used"; exit 6; }
CAPS=$E/in/experiments/0381-second-title-non-f403-hangs/boxcap0381.sh
[ -f "$CAPS" ] || { echo "no box cap at $CAPS: stop"; exit 7; }
grep -qx 'RayTracing.PPSA03671=on' "$E/input-rton.cfg" || { echo "the smoke config is not RT on"; exit 8; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
LIVE=$(sum "$W/_SaveData")
[ "$LIVE" = 377a8d456a9b4cb1 ] || { echo "live saves are $LIVE: stop and ask"; exit 5; }
rm -rf "$E/wd/_SaveData/PPSA03671"
cp -a "$S/saves-live-377a8d45" "$E/wd/_SaveData/PPSA03671"
[ "$(sum "$E/wd/_SaveData")" = "$LIVE" ] || { echo "the save copy differs"; exit 5; }
cp "$S/in-D2.cmd" "$TB/in-$TAG.cmd"
echo "top exp 0381 | $TAG: test build smoke, 120 s, RT on, box cap 135 s | $(date '+%F %T')" > "$W/BOX-LOCK"
echo "$(date '+%F %T') $TAG start: binary $(md5sum < "$TB/bin/kyty_emulator" | cut -c1-8), launcher $(md5sum < "$TB/play-pkg-0381tbs.sh" | cut -c1-8), live saves $LIVE" > "$TB/raw/$TAG-start.txt"
setsid bash "$CAPS" /exp0381/tb/bin/kyty_emulator 135 "$TB/raw/$TAG-start.txt" < /dev/null > /dev/null 2>&1 &
distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD="$TB/in-$TAG.cmd" "$TB/play-pkg-0381tbs.sh" < /dev/null > "$TB/raw/$TAG-launch.out" 2>&1
echo "launcher exit $?" >> "$TB/raw/$TAG-launch.out"
echo "$(date '+%F %T') launcher returned" >> "$TB/raw/$TAG-start.txt"
sum "$W/_SaveData" >> "$TB/raw/$TAG-start.txt"
