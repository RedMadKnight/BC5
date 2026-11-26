#!/usr/bin/env bash
# BC5 experiment 0164, route A: the empty window -> File browser -> the second title's package ->
# its start screen. Keys through drive0164.sh (ydotool), screenshots to ~/bc5-work/shots0164.
cd ~/bc5-work || exit 1
exec > ~/bc5-work/exp0164/routeA.log 2>&1
export SHOTS=0164
say() { echo "$(date +%T) $*"; }
while pgrep -f "cmake --build .*kyty_emulator" >/dev/null; do sleep 3; done
say "binary $(stat -c '%y' ~/bc5-work/kytyplus-build/src/kyty_emulator | cut -c1-19)"
if pgrep -x kyty_emulator >/dev/null; then say "another emulator is running, abort"; exit 1; fi
setsid nohup distrobox enter ubuntu -- ~/bc5-work/play-any.sh > ~/bc5-work/play-any-run.log 2>&1 &
for i in $(seq 1 30); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep 8
say "menu window up: $(pgrep -xa kyty_emulator | cut -c1-60)"
./drive0164.sh focus
sleep 0.5
./shot.sh a1-empty-window 0 >/dev/null
./drive0164.sh key 108 28            # Down, Enter: Open package (.pkg)...
sleep 1; ./shot.sh a2-browser 0 >/dev/null
./drive0164.sh key 108 108 108 108 108   # into the list, down to [pkg]
sleep 0.5; ./shot.sh a3-browser-pkg 0 >/dev/null
./drive0164.sh key 28                # enter [pkg]
sleep 0.8; ./shot.sh a4-browser-in-pkg 0 >/dev/null
./drive0164.sh key 28                # select game.pkg
sleep 0.5; ./shot.sh a5-browser-selected 0 >/dev/null
./drive0164.sh key 28                # open it: exit 76
sleep 5
say "choice: $(cat ~/bc5-work/menu/choice.txt 2>/dev/null)  recent: $(tr '\n' '|' < ~/bc5-work/menu/recent.txt 2>/dev/null)"
say "menu log tail: $(tail -n 1 ~/bc5-work/play-menu-last.log | cut -c1-120)"
for i in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
say "game emulator: $(pgrep -xa kyty_emulator | cut -c1-80)"
sleep 2; mountpoint ~/bc5-data/mnt/pkg-play
./shot.sh a6-game-10s 8 >/dev/null
sleep 35; ./shot.sh a7-game-45s 0 >/dev/null
sleep 50; ./shot.sh a8-game-95s 0 >/dev/null
say "game log head: $(head -n 1 ~/bc5-work/play-pkg-last.log | cut -c1-100)"
say "DONE routeA"
