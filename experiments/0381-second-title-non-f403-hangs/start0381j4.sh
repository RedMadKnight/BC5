#!/usr/bin/env bash
# BC5 exp 0381: one J4 start (README §17). Guard, a fresh copy of the live saves, then the launcher; it returns when the
# emulator ends. The stop comes from the laptop, attended (j4run0381.sh).
# usage, on the top session's GO and the maintainer's yes: ssh bc250 'bash -s' -- <tag> <switch 0|1> <hold_us|default> < start0381j4.sh
set -u
TAG=$1; SW=$2; HOLD=$3
W=$HOME/bc5-work; S=$W/exp0379; E=$W/exp0381
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
ENVS="BC5_EMU=$E/kyty_emulator BC5_0358_INPUT_CONFIG=$E/input-rton.cfg KYTY_BC5_INPUT_CMD=$E/in-$TAG.cmd BC5_DIRECT_DISPATCH_JOURNAL=1 BC5_DIRECT_CHAIN_BREAK_AT=12673"
[ "$SW" = 1 ] && ENVS="$ENVS BC5_DIRECT_ACB_STATE_RESTORE=1"
[ "$HOLD" = default ] || ENVS="$ENVS BC5_DIRECT_CHAIN_HOLD_US=$HOLD"
echo "top exp 0381 | $TAG: J4 switch $SW break 12673, 120 s, RT on | $(date '+%F %T')" > "$W/BOX-LOCK"
echo "$(date '+%F %T') $TAG start: binary $(md5sum < "$E/kyty_emulator" | cut -c1-8), switch $SW, hold $HOLD, live saves $LIVE" > "$E/raw/$TAG-start.txt"
# shellcheck disable=SC2086
distrobox enter ubuntu -- env $ENVS "$E/play-pkg-0381.sh" < /dev/null > "$E/raw/$TAG-launch.out" 2>&1
echo "launcher exit $?" >> "$E/raw/$TAG-launch.out"
echo "$(date '+%F %T') launcher returned" >> "$E/raw/$TAG-start.txt"
