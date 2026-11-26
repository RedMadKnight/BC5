#!/usr/bin/env python3
# BC5 exp 0381: chainscan0381.py on synthetic buffers. usage: python test_chainscan0381.py
import os
import struct
import subprocess
import sys
import tempfile

import chainscan0381 as c

HERE = os.path.dirname(os.path.abspath(__file__))


def b(dwords):
    return struct.pack("<%dI" % len(dwords), *dwords)


IB = [0xC0023F00, 0x1000, 0, 3]
CHAIN = [0xC0023F00, 0x1000, 0, (1 << 20) | 3]
SET = [0xC0017600, 0x240, 0x11]
COND = [0xC0032200, 0, 0, 0, 4]


def test(dwords, **want):
    got = c.scan(b(dwords))
    for k, v in want.items():
        assert got[k] == v, (k, v, got)


test(IB, ib=1, chain=0)
test(CHAIN, ib=1, chain=1, chain_tail=0)
test(CHAIN + SET, chain=1, chain_tail=1)
test(COND + CHAIN + SET, cond=1, chain=1, cond_chain=1, cond_ib=1)
test(COND + IB, cond_ib=1, chain=0)
test(COND + SET + SET[:0] + CHAIN, cond=1, chain=1)  # the count ends past this packet
test([0xC0083F00] + [0] * 9, ib=0, ib_other_len=1)
test(SET[:2], malformed=1)
test([0x40000000], malformed=1)
test([0xFFFF1000, 0x80000000] + SET, packets=3, malformed=0)
test([], packets=0)

with tempfile.TemporaryDirectory() as d:
    names = []
    for i, dwords in enumerate((IB, CHAIN + SET, SET)):
        p = os.path.join(d, "ib-%d.bin" % i)
        open(p, "wb").write(b(dwords))
        names.append(p)
    odd = os.path.join(d, "odd.bin")
    open(odd, "wb").write(b"abc")
    r = subprocess.run([sys.executable, os.path.join(HERE, "chainscan0381.py"), "--max-files", "2"] + names + [odd, d + "/none"],
                       capture_output=True, text=True, check=True)
    lines = r.stdout.strip().split("\n")
    assert lines[0] == "files 2, bytes %d, skipped 3, files with a CHAIN 1" % (16 + 28), r.stdout
    assert "chain 1" in lines[1], r.stdout
    assert len(lines) == 2 and "0x" not in r.stdout and d not in r.stdout, r.stdout  # counts only, no paths, no dwords
print("ok: 12 cases")
