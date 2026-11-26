#!/usr/bin/env bash
# Offset listing of a dumped shader: disf.sh with byte offsets (llvm-mc --show-encoding sizes;
# undecodable dwords, located by the warning column, are listed as <invalid> and skipped).
# usage: disoff.sh <file.bin> [max_bytes]   (stops at the first s_endpgm dword, or max_bytes)
f=$1; max=${2:-0}; t=$(mktemp ~/bc5-work/dis.XXXXXX)
python3 - "$f" "$max" > $t <<"PY"
import sys, struct
d = open(sys.argv[1], "rb").read(); mx = int(sys.argv[2])
w = struct.unpack("<%dI" % (len(d) // 4), d)
n = next((i for i, x in enumerate(w) if x == 0xbf810000), len(w) - 1) + 1
if mx: n = min(len(w), mx // 4)
print(" ".join("0x%02x" % b for b in d[:4 * n]))
PY
distrobox enter ubuntu -- llvm-mc --disassemble --show-encoding -triple=amdgcn -mcpu=gfx1013 $t >$t.out 2>$t.err
python3 - $t.out $t.err <<"PY"
import sys, re
bad = sorted((int(m.group(1)) - 1) // 5 for m in re.finditer(r":1:(\d+): warning: invalid", open(sys.argv[2]).read()))
off = 0
for line in open(sys.argv[1]):
    m = re.search(r"encoding: \[([^\]]*)\]", line)
    if not m: continue
    while bad and bad[0] <= off:
        print("%05x: <invalid dword>" % bad[0]); off = bad.pop(0) + 4
    print("%05x: %s" % (off, line.split(";")[0].strip())); off += len(m.group(1).split(","))
PY
rm -f $t $t.out $t.err
