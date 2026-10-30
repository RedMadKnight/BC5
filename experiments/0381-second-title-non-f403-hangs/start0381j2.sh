#!/usr/bin/env bash
# BC5 exp 0381: one J2 start. Guard, a fresh copy of the live saves, then the launcher with the switch on; it returns
# when the emulator ends. The stop (TERM at 120 s or the first gfx timeout) comes from the laptop, attended.
# usage, on the top session's GO: ssh bc250 'bash -s' -- <n> < start0381j2.sh
set -u
N=${1:?start number}
W=$HOME/bc5-work; S=$W/exp0379; E=$W/exp0381; TAG=J2-$N
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
[ -s "$W/BOX-LOCK" ] && ! grep -q '^top exp 0381 |' "$W/BOX-LOCK" && { echo "GUARD: BOX-LOCK: $(cat "$W/BOX-LOCK")"; exit 4; }
[ -x "$E/kyty_emulator" ] || { echo "no private binary"; exit 1; }
[ -e "$E/raw/$TAG-start.txt" ] && { echo "tag $TAG is used"; exit 6; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
LIVE=$(sum "$W/_SaveData")
[ "$LIVE" = 377a8d456a9b4cb1 ] || { echo "live saves are $LIVE: stop and ask"; exit 5; }
rm -rf "$E/wd/_SaveData/PPSA03671"
cp -a "$S/saves-live-377a8d45" "$E/wd/_SaveData/PPSA03671"
[ "$(sum "$E/wd/_SaveData")" = "$LIVE" ] || { echo "the save copy differs"; exit 5; }
cp "$S/in-D2.cmd" "$E/in-$TAG.cmd"
echo "top exp 0381 | $TAG: D2 invocation + journal + BC5_DIRECT_ACB_STATE_RESTORE=1, 120 s, RT on | $(date '+%F %T')" > "$W/BOX-LOCK"
echo "$(date '+%F %T') $TAG start: binary $(md5sum < "$E/kyty_emulator" | cut -c1-8), live saves $LIVE" > "$E/raw/$TAG-start.txt"
distrobox enter ubuntu -- env BC5_EMU="$E/kyty_emulator" BC5_0358_INPUT_CONFIG="$E/input-rton.cfg" KYTY_BC5_INPUT_CMD="$E/in-$TAG.cmd" \
    BC5_DIRECT_DISPATCH_JOURNAL=1 BC5_DIRECT_ACB_STATE_RESTORE=1 "$E/play-pkg-0381.sh" < /dev/null > "$E/raw/$TAG-launch.out" 2>&1
echo "launcher exit $?" >> "$E/raw/$TAG-launch.out"
echo "$(date '+%F %T') launcher returned" >> "$E/raw/$TAG-start.txt"
