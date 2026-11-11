#!/usr/bin/env python3
"""BC5 exp 0412 (README section 24): a thread's user-space CPU time by function over a whole perf recording
(perfgap0412.sh's .txt.gz): the functions with a host symbol, heaviest first, as a share of that thread's samples
and in seconds (one sample = 1 ms), with the guest's share on the first line.
usage: perftop0412.py <perf script .txt.gz> <tid> [<rows> default 25]"""
import collections
import gzip
import re
import sys

LINE = re.compile(r"^\s*(\d+)\s+([\d.]+):\s+([0-9a-f]+)\s+(.*?)\s+\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$")


def main():
    tid, rows = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25
    c = collections.Counter()
    n = 0
    with gzip.open(sys.argv[1], "rt", errors="replace") as f:
        for ln in f:
            m = LINE.match(ln)
            if not m or m.group(1) != tid:
                continue
            n += 1
            s, dso = re.sub(r"\+0x[0-9a-f]+$", "", m.group(4).strip()), m.group(5).rsplit("/", 1)[-1]
            c["(guest code)" if s == "[unknown]" and "kyty" not in dso and ".so" not in dso else f"{s[:110]}  [{dso[:24]}]"] += 1
    print(f"{n} samples = {n / 1000:.1f} s of user-space CPU")
    for k, v in c.most_common(rows):
        print(f"  {100 * v / n:5.1f} %  {v / 1000:6.2f} s  {k}")


if __name__ == "__main__":
    main()
