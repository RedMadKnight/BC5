#!/usr/bin/env bash
# BC5 experiment 0385: exp 0369's ana0369.sh with 0369 -> 0385 (mkkit0385.py). Older comments below keep their wording.
# BC5 experiment 0385, run K2: the analysis on the box after ab0385.sh and pl0385.py have ended. Summaries go to
# ~/bc5-work/exp0385/<tag>.*; the snapshots stay in ~/bc5-data/priv/exp0385/<tag> until they are deleted.
#   bt0362.sh on the poll log (the bursts); sn0385.py reads (each snapshot's clear size); tz0385.py (the tile test).
# usage: ana0385.sh <tag>   (on the box; no emulator running)
set -u
tag=$1
E=$HOME/bc5-work/exp0385; C=$HOME/bc5-data/priv/exp0385/$tag
pgrep "^kyty_emulator" > /dev/null && { echo "an emulator is running: stop"; exit 1; }
echo "# $(ls "$C"/*.bin | wc -l) snapshots, $(du -sh "$C" | cut -f1)"
bash "$E/bt0362.sh" "$C/events.txt" | tee "$E/$tag.bursts.txt"
distrobox enter ubuntu -- python3 -I "$E/sn0385.py" reads "$C" "$E/swz0248-z4.json" "$E/$tag.reads.json" | tee "$E/$tag.reads.txt"
distrobox enter ubuntu -- python3 -I "$E/tz0385.py" "$C" "$E/$tag.reads.json" "$E/swz0248-z4.json" > "$E/$tag.tz.txt" 2>&1
grep "^#" "$E/$tag.tz.txt"
