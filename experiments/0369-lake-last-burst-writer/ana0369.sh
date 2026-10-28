#!/usr/bin/env bash
# BC5 experiment 0369, run K2: the analysis on the box after ab0369.sh and pl0369.py have ended. Summaries go to
# ~/bc5-work/exp0369/<tag>.*; the snapshots stay in ~/bc5-data/priv/exp0369/<tag> until they are deleted.
#   bt0362.sh on the poll log (the bursts); sn0369.py reads (each snapshot's clear size); tz0369.py (the tile test).
# usage: ana0369.sh <tag>   (on the box; no emulator running)
set -u
tag=$1
E=$HOME/bc5-work/exp0369; C=$HOME/bc5-data/priv/exp0369/$tag
pgrep "^kyty_emulator" > /dev/null && { echo "an emulator is running: stop"; exit 1; }
echo "# $(ls "$C"/*.bin | wc -l) snapshots, $(du -sh "$C" | cut -f1)"
bash "$E/bt0362.sh" "$C/events.txt" | tee "$E/$tag.bursts.txt"
distrobox enter ubuntu -- python3 -I "$E/sn0369.py" reads "$C" "$E/swz0248-z4.json" "$E/$tag.reads.json" | tee "$E/$tag.reads.txt"
distrobox enter ubuntu -- python3 -I "$E/tz0369.py" "$C" "$E/$tag.reads.json" "$E/swz0248-z4.json" > "$E/$tag.tz.txt" 2>&1
grep "^#" "$E/$tag.tz.txt"
