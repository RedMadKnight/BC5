#!/usr/bin/env bash
# BC5 exp 0381: set up the J1 start-up run (exp 0379 D2's invocation plus BC5_DIRECT_DISPATCH_JOURNAL=1) in a
# private directory ~/bc5-work/exp0381: a copy of exp 0379's launcher with its paths moved to exp0381, a working
# directory of exp 0379's symlinks with a fresh copy of the live saves (377a8d45), the learned file and input config.
# Exp 0379's files are only read. Run from the laptop under our BOX-LOCK line: ssh bc250 'bash -s' < setup0381j.sh
set -u
W=$HOME/bc5-work; S=$W/exp0379; E=$W/exp0381
grep -q '^top exp 0381 |' "$W/BOX-LOCK" || { echo "GUARD: BOX-LOCK is not ours: $(cat "$W/BOX-LOCK")"; exit 4; }
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
LIVE=$(sum "$W/_SaveData"); echo "live saves $LIVE"
[ "$LIVE" = 377a8d456a9b4cb1 ] || { echo "live saves changed: stop and ask"; exit 5; }
[ -e "$E/wd" ] && { echo "$E/wd exists: stop"; exit 6; }
mkdir -p "$E/wd/_SaveData" "$E/wd/_SaveData-pkg-play"
(cd "$S/wd" && find . -maxdepth 1 -mindepth 1 -type l -print0 | xargs -0 cp -P -t "$E/wd/")
cp -a "$S/saves-live-377a8d45" "$E/wd/_SaveData/PPSA03671"
echo "copy saves $(sum "$E/wd/_SaveData")"
sed 's#exp0379#exp0381#g; s#exp 0350/0364#exp 0350/0364, exp 0381 copy#' "$S/play-pkg-0358.sh" > "$E/play-pkg-0381.sh"
chmod +x "$E/play-pkg-0381.sh"
cp "$S/direct-learned-pkg.txt" "$S/input-rton.cfg" "$E/"
cp "$S/in-D2.cmd" "$E/in-J1.cmd"
mkdir -p "$E/raw"
echo "symlinks $(find "$E/wd" -maxdepth 1 -type l | wc -l) (exp0379 $(find "$S/wd" -maxdepth 1 -type l | wc -l))"
diff <(sed 's#exp0379#exp0381#g' "$S/play-pkg-0358.sh") "$E/play-pkg-0381.sh" | head
grep -n exp0381 "$E/play-pkg-0381.sh"
md5sum "$S/kyty_emulator" "$E/play-pkg-0381.sh" "$E/direct-learned-pkg.txt" | cut -c1-8,33-
