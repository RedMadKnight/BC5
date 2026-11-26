#!/usr/bin/env python3
# BC5 exp 0381: replays one mount's BC5_MOUNT_READ_TRACE page by page: how old a repeated page really is, how many bytes went by since,
# who asked, and what an LRU of a given size would have kept. A repeat here is a page asked for again; with the page cache on it was
# evicted or never cached. Forget lines count dropped inodes. Reads from the window in seconds only.
# usage: ana-trace.py <trace> [from_s] [to_s]
import sys
from collections import Counter

PAGE = 4096
AGES = [1, 4, 16, 64, 256]
DIST_MIB = [64, 256, 512, 1024, 2048, 4096]
SIZES = [4, 32, 64, 128, 256, 1024]


def bucket(value, limits):
    for i, l in enumerate(limits):
        if value < l:
            return i
    return len(limits)


def replay(lines, lo=0.0, hi=float("inf")):
    last = {}
    total = 0
    r = {"first": 0, "again": 0, "age": [0] * (len(AGES) + 1), "dist": [0] * (len(DIST_MIB) + 1), "size": [0] * (len(SIZES) + 1),
         "pid": Counter(), "repeat_pid": Counter(), "opens": 0, "forgets": 0, "requests": 0}
    for line in lines:
        f = line.split()
        if not f:
            continue
        t = float(f[1])
        inside = lo <= t <= hi
        if f[0] == "O":
            r["opens"] += inside
        elif f[0] == "F":
            r["forgets"] += inside
        elif f[0] == "R":
            ino, offset, length, pid = int(f[2]), int(f[3]), int(f[4]), f[5]
            if length == 0:
                continue
            if inside:
                r["requests"] += 1
                r["size"][bucket(length >> 10, SIZES)] += 1
                r["pid"][pid] += length
            for page in range(offset // PAGE, (offset + length - 1) // PAGE + 1):
                key = (ino, page)
                seen = last.get(key)
                if inside:
                    if seen is None:
                        r["first"] += PAGE
                    else:
                        r["again"] += PAGE
                        r["age"][bucket(t - seen[0], AGES)] += PAGE
                        r["dist"][bucket((total - seen[1]) >> 20, DIST_MIB)] += PAGE
                        r["repeat_pid"][pid] += PAGE
                total += PAGE
                last[key] = (t, total)
    return r


def main():
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else float("inf")
    with open(sys.argv[1]) as f:
        r = replay(f, lo, hi)
    mib = lambda v: round(v / 2**20)
    print(f"requests {r['requests']}, opens {r['opens']}, forgets {r['forgets']}, first {mib(r['first'])} MiB, again {mib(r['again'])} MiB")
    print("again by age s", AGES, [mib(v) for v in r["age"]], "MiB")
    print("again by bytes since, MiB", DIST_MIB, [mib(v) for v in r["dist"]], "MiB")
    print("requests by KiB", SIZES, r["size"])
    print("bytes by pid", [(p, mib(v)) for p, v in r["pid"].most_common(8)])
    print("repeats by pid", [(p, mib(v)) for p, v in r["repeat_pid"].most_common(8)])


if __name__ == "__main__":
    main()
