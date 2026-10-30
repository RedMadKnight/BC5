#!/usr/bin/env python3
# BC5 exp 0381: J4's check (README §17). It looks at one title buffer only: size TITLE, first dispatch of 0x909977100 at
# original offset 13. J3's rule counted any buffer, and the others carry the CS prefix with the switch off.
# DIRECT: that buffer in a job's first segment, with an acb as the previous job. It prints the buffer's own prefix, the
# USER_DATA_0 in it, and the last acb dispatch's user data 0 before the job (the value the buffer would inherit).
# usage: python3 j4check0381.py direct.log [title dwords]
import re
import sys

JOB = re.compile(r"^job (\d+) (\S+): (\d+) dwords, (\d+) segments, ring (-?\d+), previous job (\S+)")
SEG = re.compile(r"^\s+job (\d+) seg (\d+): off (\d+) prefix (\d+) n (\d+) prefix ud0 (\S+)")
DIS = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+).* job (\d+) seg (-?\d+) orig (\d+)")
TIM = re.compile(r"^timing: t ([0-9.]+) s")
PGM = "909977100"
ORIG = 13


def report(lines, title=12673):
    jobs, segs, seen = {}, {}, set()
    found = []
    acb_ud0 = None
    t = 0.0
    n_lines = 0
    for line in lines:
        m = TIM.match(line)
        if m:
            t = float(m.group(1))
            continue
        m = JOB.match(line)
        if m:
            jobs[int(m.group(1))] = (int(m.group(4)), m.group(6))
            continue
        m = SEG.match(line)
        if m:
            segs[(int(m.group(1)), int(m.group(2)))] = (int(m.group(4)), int(m.group(5)), m.group(6))
            continue
        m = DIS.match(line)
        if not m:
            continue
        n_lines += 1
        kind, pgm, ud0, job, seg, orig = m.group(1), m.group(3), int(m.group(4), 16), int(m.group(5)), int(m.group(6)), int(m.group(7))
        if kind.startswith("acb"):
            acb_ud0 = ud0
        first = (job, seg) not in seen
        seen.add((job, seg))
        if first and pgm == PGM and orig == ORIG and segs.get((job, seg), (0, 0, ""))[1] == title:
            found.append((t, job, seg, acb_ud0))
    if not jobs or not n_lines:
        return ["verdict: eligibility unverified (no job or segment identity in this journal)"]
    out = []
    direct = 0
    for t, job, seg, acb in found:
        count, prev = jobs.get(job, (0, "?"))
        prefix, _, pud0 = segs[(job, seg)]
        ok = seg == 0 and prev == "acb"
        direct += ok
        out.append("buffer t %.2f job %d seg %d/%d previous job %s, prefix %d dwords, prefix ud0 %s, last acb ud0 %s: %s"
                   % (t, job, seg, count, prev, prefix, pud0, "none" if acb is None else "0x%x" % acb, "DIRECT" if ok else "not direct"))
    out.append("buffers %d, direct %d" % (len(found), direct))
    return out


if __name__ == "__main__":
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 12673
    with open(sys.argv[1], errors="replace") as f:
        print("\n".join(report(f, size)))
