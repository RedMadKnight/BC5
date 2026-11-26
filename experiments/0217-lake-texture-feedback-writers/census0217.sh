#!/usr/bin/env bash
# BC5 experiment 0217: which of the title's programs write memory (stores, atomics), from the private disassembly
# listings ~/bc5-data/priv/<address>.dis (llvm-mc -mcpu=gfx1013 text from earlier experiments; the title's code, never
# copied off the box). Prints only counts: per program that writes memory, its number of "exp mrt" exports (a pixel
# program has them) and its store/atomic mnemonics with counts; then the totals per mnemonic. Run on the box under a
# short BOX-LOCK line (read-only, a few seconds), as on 2026-10-22 20:25.
# usage: census0217.sh [listing dir]
set -u
P=${1:-$HOME/bc5-data/priv}
cd "$P" || exit 1
for f in *.dis; do
  w=$(grep -oE "\b(image|buffer|global|flat)_(store|atomic)[a-z_0-9]*|\b(image|buffer|global|flat)_[a-z_0-9]*atomic[a-z_0-9]*" "$f" |
      sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
  x=$(grep -cE "\bexp\s+mrt" "$f")
  [ -n "$w" ] && echo "${f%.dis} mrt-exports=$x $w"
done | sort > /tmp/census0217.txt
echo "listings: $(ls *.dis | wc -l); programs that store or use atomics: $(wc -l < /tmp/census0217.txt)"
awk '{for (i = 3; i <= NF; i++) {split($i, a, ":"); c[a[1]] += 1}} END {for (k in c) print c[k], k}' /tmp/census0217.txt | sort -rn
echo "-- programs with atomics:"
grep -i "atomic" /tmp/census0217.txt
echo "-- pixel-type programs (exp mrt) that also store or use atomics:"
awk '$2 != "mrt-exports=0"' /tmp/census0217.txt
rm -f /tmp/census0217.txt
