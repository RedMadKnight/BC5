#!/usr/bin/env bash
# BC5 experiment 0362: the analysis of one run, on the box after ab0362.sh and pl0362.py have ended. Summaries go to
# ~/bc5-work/exp0362/<tag>.*; the snapshots stay in ~/bc5-data/priv/exp0362/<tag> until cl0362.sh deletes them.
#   sn0362.py reads -> fr0354.py (the journal's lag and widths) -> sn0362.py ana; fi0362.py on the journal.
# usage: ana0362.sh <tag> [FLOOR]   (on the box; no emulator running)
set -u
tag=$1; FLOOR=${2:-0.03}
E=$HOME/bc5-work/exp0362; C=$HOME/bc5-data/priv/exp0362/$tag; R=$E/r-$tag
pgrep "^kyty_emulator" > /dev/null && { echo "an emulator is running: stop"; exit 1; }
J=$(cat "$R/journal-dir.txt")/direct.log
[ -s "$J" ] || { echo "no journal at $J: stop"; exit 1; }
echo "# journal $J, $(stat -c %s "$J") bytes; $(ls "$C"/*.bin | wc -l) snapshots, $(du -sh "$C" | cut -f1)"
distrobox enter ubuntu -- python3 -I "$E/sn0362.py" reads "$C" "$E/swz0248-z4.json" "$E/$tag.reads.json" | tee "$E/$tag.reads.txt"
python3 -I "$E/fr0354.py" "$J" "$E/$tag.reads.json" "$E/$tag.fr.json" | tee "$E/$tag.fr.txt"
distrobox enter ubuntu -- python3 -I "$E/sn0362.py" ana "$C" "$E/$tag.reads.json" "$E/$tag.fr.json" "$E/swz0248-z4.json" "$E/$tag.ana.json" "$FLOOR" > "$E/$tag.ana.txt"
grep "^#" "$E/$tag.ana.txt"
sed -n '/^# class pairs/,$p' "$E/$tag.ana.txt"
python3 -I "$E/fi0362.py" "$J" "$E/$tag.fi.json" > "$E/$tag.fi.txt"
head -40 "$E/$tag.fi.txt"
