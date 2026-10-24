#!/usr/bin/env bash
# BC5 experiment 0260: the catch run, the maintainer's own play of the second title with the private binary whose timeout
# probe journals a stuck buffer's waits, label writes and dispatches and syncs them (patch0260.py). He starts it
# himself, from a terminal on the box (Konsole): ~/bc5-work/exp0260/play0260.sh
#   1. the box must be free: no BOX-LOCK, no emulator;
#   2. his live saves (~/bc5-work/_SaveData) are copied aside to ~/bc5-work/exp0260/saves-before-play-<time> (kept,
#      not restored afterwards);
#   3. a BOX-LOCK line naming him (MAINTAINER PLAYING: no session touches the box; the laptop's stream0260.sh reads
#      only the kernel log and the probe's journal lines, as the box supervisor arranged for this run);
#   4. the normal launcher, ~/bc5-work/play-pkg.sh, with its current defaults (the held tail, the CS prefix, the tiler
#      pool, BC5_DIRECT_TIMEOUT_PROBE=1 as it already sets) and one difference: the binary ~/bc5-work/exp0260/kyty_emulator;
#   5. when the game exits (from its menu, or the window closed), the lock is removed.
# After a machine-down nothing is lost that matters: the probe's dump and its journal lines are synced to disk.
set -u
E=$HOME/bc5-work/exp0260; LOCK=$HOME/bc5-work/BOX-LOCK
if [ -s "$LOCK" ]; then echo "Box zajęty: $(cat "$LOCK")"; exit 1; fi
if pgrep -x kyty_emulator > /dev/null; then echo "Emulator już działa."; exit 1; fi
[ -x "$E/kyty_emulator" ] || { echo "Brak binarki $E/kyty_emulator"; exit 1; }
S=$E/saves-before-play-$(date +%H%M%S)
cp -a "$HOME/bc5-work/_SaveData" "$S" || { echo "Kopia zapisów się nie udała: przerywam."; exit 1; }
sync
echo "Zapisy skopiowane do $S ($(du -sh "$S" | cut -f1))."
echo "MAINTAINER PLAYING | exp 0260: timeout probe catch run (exp0260 binary, launcher defaults) | start $(date +%H:%M)" > "$LOCK"
trap 'grep -q "^MAINTAINER PLAYING | exp 0260" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT # a closed Konsole or Ctrl+C leaves no stale lock
mkdir -p "$E/raw"
echo "$(date '+%F %T') start, binary md5 $(md5sum < "$E/kyty_emulator" | cut -c1-8), launcher md5 $(md5sum < "$HOME/bc5-work/play-pkg.sh" | cut -c1-8)" > "$E/raw/play-$(date +%H%M).txt"
sync
distrobox enter ubuntu -- env BC5_EMU="$E/kyty_emulator" BC5_DIRECT_TIMEOUT_PROBE=1 "$HOME/bc5-work/play-pkg.sh"
rc=$?
grep -q "^MAINTAINER PLAYING | exp 0260" "$LOCK" 2> /dev/null && rm -f "$LOCK"
echo "Gra zakończona (kod $rc), BOX-LOCK usunięty. Dziękuję!"
