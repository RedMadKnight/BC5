#!/usr/bin/env python3
"""BC5 experiment 0392: what the TF ring held at each sF, in numbers only. The ring's words are 32-bit floats (F597).
Per snapshot: "<c>.<f>.sF zero <share> low <share of 0 < x < 1> one <share of x == 1> high <share of 1 < x <= 64> odd <share of the rest>
blocks <64-KiB blocks with no non-zero word>". The rest of a run's reading joins these to its frames.
usage: tf0392.py <dir of c<NN>.f<k>.sF.bin>"""
import os
import sys

import numpy as np


def summary(raw):
    a = np.frombuffer(raw, dtype="<f4")
    n = max(a.size, 1)
    zero = int(np.count_nonzero(a == 0))
    low = int(np.count_nonzero((a > 0) & (a < 1)))
    one = int(np.count_nonzero(a == 1))
    high = int(np.count_nonzero((a > 1) & (a <= 64)))
    odd = a.size - zero - low - one - high
    block = 64 << 8  # 64 KiB in words
    empty = sum(1 for k in range(0, a.size, block) if not np.any(a[k:k + block]))
    return f"zero {zero / n:.4f} low {low / n:.4f} one {one / n:.4f} high {high / n:.4f} odd {odd / n:.4f} blocks {empty}"


def main():
    d = sys.argv[1]
    names = sorted(x for x in os.listdir(d) if x.endswith(".sF.bin"))
    for name in names:
        with open(os.path.join(d, name), "rb") as f:
            print(name[:-4], summary(f.read()))
    print(f"# {len(names)} snapshots")


if __name__ == "__main__":
    main()
