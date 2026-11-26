#!/usr/bin/env bash
# BC5 exp 0388, in a slot from the top session: the third cycle's exposure and frame rate, read only, offsets and counts
# only, from the private raw directory. Prints one line per run; writes nothing.
# usage: ssh bc250 'bash -s' < read0388.sh
set -u
export LC_ALL=C
pgrep '^kyty_emulator' > /dev/null && { echo "read0388: an emulator runs"; exit 1; }
cd ~/bc5-work/exp0388/run/raw || exit 1
for t in G4 G5 G6 F6 F7 F8 H1 H2 H3 H4 H5 J1 J2 J3 J4 J5 K1 K2 K3 L1 L2 L3; do
    fps=$(awk '$1 >= 120 && $1 < 170 { s += $2; n++ } END { if (n) printf "%.1f", s / n / 10; else printf "NA" }' "$t-flips-per-10s.txt" 2> /dev/null)
    spin=$(grep -a 'push spin' "$t-play.log" 2> /dev/null | tail -1 | cut -c15-120)
    nice=$(grep 'Job Hi' "$t-nice.txt" 2> /dev/null | tr -s ' ' | tr '\n' ';')
    echo "$t $(cut -c1-40 "$t-end.txt" 2> /dev/null) | flips/s ${fps:-NA} | ${spin:-no push spin line} | nice ${nice:-none}"
done
tail -1 J5-cpuidle-end.txt 2> /dev/null | cut -c1-100
grep -h '/name:\|/latency:' J5-cpuidle-end.txt 2> /dev/null | cut -d/ -f8- | head -12
