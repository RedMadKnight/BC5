#!/usr/bin/env bash
# BC5 experiment 0250: the read-only box step, no emulator (top session's grant, 2026-10-23, after the BVH session's
# exp 0249): under this experiment's BOX-LOCK line,
#  1. whether the two binaries used for the lake journals carry BC5_DIRECT_DRAW_JOURNAL_EVERY: exp 0194's
#     (edit0194.py adds it) and exp 0245's private one (built from the shared tree, patch 0001 has no such switch);
#  2. db0250.py over H1's journal (exp 0248, filtered on the full-screen draw and four depth-only writers) and Z2's
#     (exp 0245, unfiltered, about three frames): the depth buffer's size, HTILE base, DB_Z_INFO fields and the entries
#     before each frame's first depth write.
# Journals stay where they are (~/bc5-data/captures); only the summaries are written, to ~/bc5-work/exp0250.
# usage: grep0250.sh   (on the box, from SSH)
set -u
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q "exp 0250 | read-only" ~/bc5-work/BOX-LOCK 2>/dev/null || { echo "no exp 0250 lock line: stop"; exit 1; }
E=$HOME/bc5-work/exp0250
G=$HOME/bc5-work/exp0245/gfx10.json
for b in "$HOME/bc5-work/exp0194/kyty_emulator" "$HOME/bc5-work/exp0245/kyty_emulator" "$HOME/bc5-work/kytyplus-build/kyty_emulator"; do
  [ -e "$b" ] || { echo "$b: missing"; continue; }
  echo "$b: $(stat -c '%s bytes, %y' "$b"); BC5_DIRECT_DRAW_JOURNAL_EVERY strings: $(grep -a -o BC5_DIRECT_DRAW_JOURNAL_EVERY "$b" | wc -l)"
done | tee "$E/binaries.txt"
for run in "H1 play-20261023-2113" "Z2 play-20261023-2023"; do
  set -- $run
  L=$HOME/bc5-data/captures/$2/gc/direct.log
  echo "$1: $L $(du -h "$L" | cut -f1)"
  nice -n 19 python3 -I "$E/db0250.py" "$L" "$G" > "$E/$1.surf.txt" 2>&1
  wc -l < "$E/$1.surf.txt"
done
