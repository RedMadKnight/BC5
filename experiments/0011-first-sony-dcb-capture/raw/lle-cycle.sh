#!/usr/bin/env bash
# BC5 track B iteration: rebuild kyty_emulator, run ASTRO BOT with LLE libSceAgc + /dev/gc, summarise.
# usage: lle-cycle.sh [run seconds] [tail lines]
set -u
RUN=${1:-120}
TAIL=${2:-60}
cd ~/bc5-work/kytyplus-build
cmake --build . --target kyty_emulator -j8 2>&1 | grep -E "error|FAILED" | head -20
echo "build exit ${PIPESTATUS[0]}"
SHADPS4_SYSMODULES_PACK_DIR=/home/kjaniszewski/bc5-data/mnt/PPSA21567/fakelib KYTY_GUEST_MEMORY_MB=13824 SDL_VIDEODRIVER=wayland RUN_SECONDS=$RUN ~/bc5-work/run-astro-kytyplus.sh 2>&1 | tail -2
CAP=$(cat ~/bc5-work/last-kytyplus)
F="$CAP/guest-printf.txt"
echo "== $CAP: $(wc -l < "$F") lines, gc dumps: $(ls "$CAP/gc" | wc -l), kyty cb: $(ls "$CAP/cb" | wc -l) =="
grep -n -E "bc5]|bc5-gc|Open device|Unresolved import stub called|recent stubbed|Access violation|exception_address|stack fail|stack_chk_fail caller module|GAME:|Load end" "$F" | grep -v "PRINT" | cut -c1-190 | tail -"$TAIL"
tail -4 "$CAP/kyty.log" | cut -c1-160
