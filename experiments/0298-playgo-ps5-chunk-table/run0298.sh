#!/usr/bin/env bash
# BC5 experiment 0298: the second title on the private PlayGo build (af40804e) for the maintainer's test from his
# slot 4, through play-pkg-0298.sh (play-pkg.sh with that binary, its own log and the module pack without
# libScePlayGo.sprx). Started over ssh as a user unit by the supervisor; the saves are copied first.
set -u
E=~/bc5-work/exp0298; L=~/bc5-work/BOX-LOCK
[ "$(md5sum < "$E/kyty_emulator" | cut -c1-8)" = af40804e ] || { echo "the private binary is not af40804e"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is already running"; exit 1; }
if [ -s "$L" ] && ! grep -q "^supervisor | PlayGo" "$L"; then echo "the box is locked: $(cat "$L")"; exit 1; fi
T=$(date +%H%M)
cp -a ~/bc5-work/_SaveData/PPSA03671 "$E/saves-before-test-$T"
echo "MAINTAINER PLAYING | exp 0298 PlayGo test (private build af40804e, play-pkg-0298.sh, supervisor) | start $(date +%H:%M) | until the maintainer ends" > "$L"
/usr/bin/distrobox enter ubuntu -- bash "$E/play-pkg-0298.sh" "$@"
RC=$?
grep -q "^MAINTAINER PLAYING | exp 0298" "$L" 2> /dev/null && : > "$L"
echo "exit $RC; PlayGo lines: $(grep -a -c 'bc5 playgo' "$E/play-0298.log" 2> /dev/null)"
exit $RC
