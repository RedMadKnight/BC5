#!/usr/bin/env bash
# BC5 experiment 0210: the maintainer's long play with the reflections on (shared build). Checks the box is free,
# copies the live saves aside (no restore afterwards: the progress is his), takes BOX-LOCK and starts the title
# fullscreen on the box display. stop.sh releases the lock afterwards.
set -u
cd ~/bc5-work || exit 1
pgrep -x kyty_emulator >/dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -e BOX-LOCK ] && { echo "BOX-LOCK held: $(cat BOX-LOCK)"; exit 1; }
T=$(date +%H%M%S)
cp -a _SaveData/PPSA03671 "exp0210/saves-before-$T" && echo "saves copied to exp0210/saves-before-$T"
echo "second-title-why-the-bvh | long play exp 0210 (FLAT_APERTURE+SKIP_PGM=1+AMM_PRT, maintainer) | start $(date +%H:%M) | until ~$(date -d +40min +%H:%M)" > BOX-LOCK
uptime -s > exp0210/boot.txt
date +%T > exp0210/start.txt
setsid nohup distrobox enter ubuntu -- /usr/bin/env BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_SKIP_PGM=1 BC5_DIRECT_AMM_PRT=1 \
    /home/kjaniszewski/bc5-work/play-any.sh /home/kjaniszewski/bc5-data/pkg/game.pkg > exp0210/launcher.out 2>&1 < /dev/null &
for _ in $(seq 1 60); do pgrep -f "kyty_emulator --game" >/dev/null && break; sleep 1; done
pgrep -af "kyty_emulator --game" | cut -c1-100
cat BOX-LOCK
