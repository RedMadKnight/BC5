#!/usr/bin/env bash
# BC5 experiment 0226: the maintainer's own play with ADR 0013's held tail. He starts it himself, from a terminal on
# the box (Konsole): ~/bc5-work/exp0226/play0226.sh
#   1. the box must be free: no BOX-LOCK, no emulator;
#   2. his live saves (~/bc5-work/_SaveData) are copied aside to ~/bc5-work/exp0226/saves-before-play-<time> (kept,
#      not restored afterwards);
#   3. a BOX-LOCK line naming him (MAINTAINER PLAYING: no session touches the box, only the kernel-log stream);
#   4. the normal launcher, ~/bc5-work/play-pkg.sh, with its current defaults (reflections on, AMM_PRT, the APR
#      read-ahead) and two differences: the binary ~/bc5-work/exp0226/kyty_emulator and BC5_DIRECT_HOLD_TAIL=1;
#   5. when the game exits (from its menu, or the window closed), the lock is removed.
set -u
E=$HOME/bc5-work/exp0226; LOCK=$HOME/bc5-work/BOX-LOCK
if [ -s "$LOCK" ]; then echo "Box zajęty: $(cat "$LOCK")"; exit 1; fi
if pgrep -x kyty_emulator > /dev/null; then echo "Emulator już działa."; exit 1; fi
[ -x "$E/kyty_emulator" ] || { echo "Brak binarki $E/kyty_emulator"; exit 1; }
S=$E/saves-before-play-$(date +%H%M%S)
cp -a "$HOME/bc5-work/_SaveData" "$S" || { echo "Kopia zapisów się nie udała: przerywam."; exit 1; }
echo "Zapisy skopiowane do $S ($(du -sh "$S" | cut -f1))."
echo "MAINTAINER PLAYING | exp 0226: held tail (BC5_DIRECT_HOLD_TAIL=1), exp0226 binary, current launcher defaults | start $(date +%H:%M)" > "$LOCK"
trap 'grep -q "^MAINTAINER PLAYING | exp 0226" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT # a closed Konsole or Ctrl+C leaves no stale lock
echo "$(date '+%F %T') start" > "$E/raw/play-$(date +%H%M).txt"
distrobox enter ubuntu -- env BC5_EMU="$E/kyty_emulator" BC5_DIRECT_HOLD_TAIL=1 "$HOME/bc5-work/play-pkg.sh"
rc=$?
grep -q "^MAINTAINER PLAYING | exp 0226" "$LOCK" 2> /dev/null && rm -f "$LOCK"
echo "Gra zakończona (kod $rc), BOX-LOCK usunięty. Dziękuję!"
