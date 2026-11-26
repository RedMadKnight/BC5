#!/usr/bin/env python3
# BC5 exp 0381: J3's eligibility and restore checks over a direct.log from the journal of patch0381-bc5LleAgc.diff.
# A target is a dispatch of 0x909977100 in the first segment of a job, at an ORIGINAL title-buffer offset below 64, as
# the first dispatch of that segment, with an acb as the previous job. Its restore is the USER_DATA_0 in that very
# segment's emitted prefix. The journal's chain offset (`at`) is not used. A log without job lines is "unverified".
# Replaces j2check0381.py and j2job0381.py, which filtered on the chain offset (Codex review REVIEW-06-J2).
# usage: python3 j3check0381.py direct.log
import re
import sys

JOB = re.compile(r"^job (\d+) (\S+): (\d+) dwords, (\d+) segments, ring (-?\d+), previous job (\S+)")
SEG = re.compile(r"^\s+job (\d+) seg (\d+): off (\d+) prefix (\d+) n (\d+) prefix ud0 (\S+)")
DIS = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+).* job (\d+) seg (-?\d+) orig (\d+)")
TIM = re.compile(r"^timing: t ([0-9.]+) s")
PGM = "909977100"
LIMIT = 64


def check(lines):
    jobs, segs, seen = {}, {}, set()
    targets = []
    n_jobs = n_lines = 0
    t = 0.0
    for line in lines:
        m = TIM.match(line)
        if m:
            t = float(m.group(1))
            continue
        m = JOB.match(line)
        if m:
            n_jobs += 1
            jobs[int(m.group(1))] = (m.group(2), int(m.group(3)), int(m.group(4)), m.group(6))
            continue
        m = SEG.match(line)
        if m:
            segs[(int(m.group(1)), int(m.group(2)))] = (int(m.group(4)), int(m.group(5)), m.group(6))
            continue
        m = DIS.match(line)
        if not m:
            continue
        n_lines += 1
        pgm, job, seg, orig = m.group(3), int(m.group(5)), int(m.group(6)), int(m.group(7))
        first = (job, seg) not in seen
        seen.add((job, seg))
        if first and pgm == PGM and orig < LIMIT:
            targets.append((t, job, seg, orig, int(m.group(4), 16)))
    return jobs, segs, targets, n_jobs, n_lines


def report(lines):
    jobs, segs, targets, n_jobs, n_lines = check(lines)
    out = ["jobs %d, dispatch lines with identity %d" % (n_jobs, n_lines)]
    if n_jobs == 0 or n_lines == 0:
        out.append("verdict: eligibility unverified (no job or segment identity in this journal)")
        return out
    eligible = 0
    for t, job, seg, orig, ud0 in targets:
        kind, dwords, count, prev = jobs.get(job, ("?", 0, 0, "?"))
        prefix, n, pud0 = segs.get((job, seg), (0, 0, "?"))
        ok = seg == 0 and prev == "acb"
        eligible += ok
        out.append("target t %.2f job %d seg %d/%d orig %d title %d dwords, previous job %s, prefix %d dwords, prefix ud0 %s, tracker ud0 0x%x: %s"
                   % (t, job, seg, count, orig, n, prev, prefix, pud0, ud0, "ELIGIBLE" if ok else "not eligible"))
    out.append("targets %d, eligible %d" % (len(targets), eligible))
    return out


if __name__ == "__main__":
    with open(sys.argv[1], errors="replace") as f:
        print("\n".join(report(f)))
