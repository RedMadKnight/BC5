#!/usr/bin/env python3
# BC5 experiment 0390: the first AddressSanitizer report of one harness run, shortened: the error, the crashing frames
# and the summary line, with paths cut to file names. usage: stacks0390.py <harness output> [frames]
import re
import sys

keep = int(sys.argv[2]) if len(sys.argv) > 2 else 6
frames = 0
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.rstrip()
    if "ERROR: AddressSanitizer" in line or "caused by a" in line or line.startswith("busy:"):
        print(line[:170])
    elif re.match(r"\s+#\d+ ", line) and frames < keep:
        frames += 1
        line = re.sub(r"[A-Za-z]:\\[^ :]*\\", "", line)
        line = re.sub(r"0x[0-9a-f]{8,} ", "", line)
        line = re.sub(r"\(h\.exe\+0x[0-9a-f]+\)", "", line)
        print(line[:150])
