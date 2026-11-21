#!/usr/bin/env bash
# BC5 experiment 0438: decode xref438.py's candidate windows with the host's objdump and keep the instructions whose
# RIP-relative operand is the target (objdump prints the target in its "# 0x..." comment). Private output only.
# usage: bash xref438-dis.sh [DIR]   (DIR default ~/bc5-data/private/exp0438-xref)
set -u
D=${1:-$HOME/bc5-data/private/exp0438-xref}
T=$(sed -n 's/^target \(0x[0-9a-f]*\);.*/\1/p' "$D/index.txt")
[ -n "$T" ] || { echo "no target in $D/index.txt"; exit 1; }
: > "$D/hits.txt"; chmod 600 "$D/hits.txt"
sed -n 's/^\(0x[0-9a-f]*\) imm [0-9] window \(0x[0-9a-f]*\)-.*/\1 \2/p' "$D/index.txt" | while read -r v a; do
  f=$D/cand-${v#0x}.bin
  # every start in the 64 bytes before the displacement: one decode lines up with the instruction stream
  for s in $(seq 0 63); do
    st=$((a + s)); [ "$st" -le "$((v))" ] || break
    objdump -D -b binary -m i386:x86-64 --adjust-vma="$a" --start-address=$st "$f" 2> /dev/null \
      | grep -i "# $T\b\|# 0x0*${T#0x}\b" | head -1
  done | sort | uniq -c | sort -rn | head -1 | sed "s/^/cand $v: /" >> "$D/hits.txt"
done
echo "$(wc -l < "$D/hits.txt") candidates decoded -> $D/hits.txt"
