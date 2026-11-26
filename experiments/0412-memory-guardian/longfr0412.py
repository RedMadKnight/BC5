#!/usr/bin/env python3
"""BC5 exp 0412 (README section 25): what the host's threads did in the long frames of the play phase.
From the gap lines (BC5_GUARD_GAP_STAT=33): for the frames of each length class, the mean milliseconds per frame of
every host cause, per thread slot, beside the mean frame length.
usage: longfr0412.py <gaps file> [<load at s> default 104]"""
import collections
import re
import sys

GAP = re.compile(r"gap \(exp 0412, tag gp412\): t ([\d.]+) s mono ([\d.]+): ([\d.]+) ms since the last flip(.*)")


def main():
    load_at = float(sys.argv[2]) if len(sys.argv) > 2 else 104.0
    rows = []
    for ln in open(sys.argv[1], errors="replace"):
        m = GAP.search(ln)
        if not m or float(m.group(1)) < load_at + 28:
            continue
        host = {}
        for part in m.group(4).split(" | ")[1:]:
            name, _, rest = part.partition(":")
            for c in rest.split(","):
                if c.strip():
                    k, v = c.strip().rsplit(" ", 1)
                    host[(name.strip(), k)] = float(v)
        rows.append((float(m.group(3)), host))
    for lo, hi in ((33, 50), (50, 100), (100, 1e9)):
        fr = [r for r in rows if lo < r[0] <= hi]
        if not fr:
            continue
        mean = sum(r[0] for r in fr) / len(fr)
        acc = collections.Counter()
        for _, h in fr:
            for k, v in h.items():
                acc[k] += v
        print(f"frames {lo}-{hi if hi < 1e8 else 'up'} ms: {len(fr)}, mean {mean:.1f} ms; mean ms per frame by thread and cause (0.5 ms and more):")
        by = collections.defaultdict(list)
        for (slot, cause), v in acc.most_common():
            if v / len(fr) >= 0.5:
                by[slot].append(f"{cause} {v / len(fr):.1f}")
        for slot, items in by.items():
            print(f"   {slot}: " + ", ".join(items))


if __name__ == "__main__":
    main()
