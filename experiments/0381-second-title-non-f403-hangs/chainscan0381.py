#!/usr/bin/env python3
# BC5 exp 0381: count INDIRECT_BUFFER CHAINs in dumped title command buffers (little-endian dwords). Read-only. It prints
# counts and file sizes only, never a dword of a buffer or an address: nothing it writes is title data.
# CHAIN: bit 20 of the IB's size dword (AMD PAL c5e8000 gfx9_plus_merged_f32_pfp_pm4_packets.h:2580). Nested targets are not
# followed: a dump holds one buffer, so a CHAIN inside a target is not seen.
# Limits: at most --max-files files and --max-bytes bytes in all, and each file at most 64 MiB; files over the limits are
# counted as skipped, and a summary line says so. The walk stops at a malformed packet, and that is counted.
# usage: python3 chainscan0381.py [--max-files N] [--max-bytes N] <file>...   (exit 0 even with hits; 2 on bad use)
import argparse
import os
import struct
import sys

MAX_FILE = 64 << 20


def scan(data):
    """Counts for one buffer."""
    n = len(data) // 4
    ib = struct.unpack("<%dI" % n, data[: n * 4])
    c = dict(packets=0, ib=0, chain=0, chain_tail=0, cond_ib=0, cond_chain=0, ib_other_len=0, cond=0, malformed=0)
    i = 0
    cond_end = 0
    while i < n:
        h = ib[i]
        t = h >> 30
        count = (h >> 16) & 0x3fff
        ln = 1 if (t in (1, 2) or count == 0x3fff) else count + 2
        if t == 1 or i + ln > n:
            c["malformed"] += 1
            break
        c["packets"] += 1
        op = (h >> 8) & 0xff
        if t == 3 and op == 0x22:
            c["cond"] += 1
            if ln >= 5:
                cond_end = max(cond_end, i + ln + (ib[i + 4] & 0x3fff))
        elif t == 3 and op == 0x3f:
            if ln != 4:
                c["ib_other_len"] += 1
            else:
                c["ib"] += 1
                under = i < cond_end
                c["cond_ib"] += under
                if ib[i + 3] & (1 << 20):
                    c["chain"] += 1
                    c["cond_chain"] += under
                    c["chain_tail"] += i + ln < n
        i += ln
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-files", type=int, default=5000)
    ap.add_argument("--max-bytes", type=int, default=2 << 30)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    total = {}
    files = read = skipped = with_chain = 0
    for f in a.files:
        try:
            size = os.path.getsize(f)
        except OSError:
            skipped += 1
            continue
        if files >= a.max_files or read + size > a.max_bytes or size > MAX_FILE or size % 4 != 0:
            skipped += 1
            continue
        with open(f, "rb") as fh:
            c = scan(fh.read())
        files += 1
        read += size
        with_chain += c["chain"] > 0
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
    print("files %d, bytes %d, skipped %d, files with a CHAIN %d" % (files, read, skipped, with_chain))
    print(" ".join("%s %d" % kv for kv in sorted(total.items())))


if __name__ == "__main__":
    sys.exit(main())
