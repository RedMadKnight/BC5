#!/usr/bin/env bash
# BC5 experiment 0365: the analysis of one run, on the box after ab0365.sh and pl0365.py have ended. Summaries go to
# ~/bc5-work/exp0365/<tag>.*; the snapshots stay in ~/bc5-data/priv/exp0365/<tag> until they are deleted.
#   sn0365.py reads -> sn0365.py ana; the poll log's bursts by bt0362.sh.
# usage: ana0365.sh <tag> [FLOOR]   (on the box; no emulator running)
set -u
tag=$1; FLOOR=${2:-0.03}
E=$HOME/bc5-work/exp0365; C=$HOME/bc5-data/priv/exp0365/$tag
pgrep "^kyty_emulator" > /dev/null && { echo "an emulator is running: stop"; exit 1; }
echo "# $(ls "$C"/*.bin | wc -l) snapshots, $(du -sh "$C" | cut -f1)"
bash "$E/bt0362.sh" "$C/events.txt" | tee "$E/$tag.bursts.txt"
distrobox enter ubuntu -- python3 -I "$E/sn0365.py" reads "$C" "$E/swz0248-z4.json" "$E/$tag.reads.json" | tee "$E/$tag.reads.txt"
distrobox enter ubuntu -- python3 -I "$E/sn0365.py" ana "$C" "$E/$tag.reads.json" "$E/swz0248-z4.json" "$E/$tag.ana.json" "$FLOOR" > "$E/$tag.ana.txt" 2>&1
grep "^#" "$E/$tag.ana.txt"
sed -n '/^# means by/,$p' "$E/$tag.ana.txt" | cut -c1-900
