#!/usr/bin/env python3
# BC5 exp 0381: J4's check (README §17). It looks at one title buffer only: size TITLE, first dispatch of 0x909977100 at
# original offset 13. DIRECT: that buffer in a job's first segment, with an acb as the previous job.
# INHERITED: what that buffer would take from before it. Walking the job ids back from the predecessor, the first acb
# whose final USER_DATA_0 is known gives the value; "none" jobs are passed over; a final "unknown", or a job missing from
# the journal, gives UNKNOWN; reaching a dcb gives "dcb" (no acb's value is carried). Nothing depends on journal line
# order, and no dispatch line is read for this (Codex's J4 review). This is the host's view, in the host's submission
# order: not a capture of what the GPU consumed.
# EXPOSED: DIRECT with a known inherited value other than 0x11. Only EXPOSED counts for §17's outcomes.
# usage: python3 j4check0381.py direct.log [title dwords]
import re
import sys

JOB = re.compile(r"^job (\d+) (\S+): (\d+) dwords, (\d+) segments, ring (-?\d+), previous job (\S+)(?: (\d+), final ud0 (\S+))?")
SEG = re.compile(r"^\s+job (\d+) seg (\d+): off (\d+) prefix (\d+) n (\d+) prefix ud0 (\S+)")
DIS = re.compile(r"^\s+(\S+) dispatch op \w+ at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+).* job (\d+) seg (-?\d+) orig (\d+)")
TIM = re.compile(r"^timing: t ([0-9.]+) s")
PGM = "909977100"
ORIG = 13
WANT = 0x11
DEPTH = 256


def inherited(jobs, job):
    prev = jobs[job]["prev_id"]
    for _ in range(DEPTH):
        j = jobs.get(prev)
        if j is None:
            return "UNKNOWN"
        if not j["kind"].startswith("acb"):
            return "dcb"
        final = j["final"]
        if final == "none":
            prev = j["prev_id"]
            continue
        return "UNKNOWN" if final in (None, "unknown", "-") else final
    return "UNKNOWN"


def report(lines, title=12673):
    jobs, segs, seen = {}, {}, set()
    found = []
    t = 0.0
    n_lines = 0
    for line in lines:
        m = TIM.match(line)
        if m:
            t = float(m.group(1))
            continue
        m = JOB.match(line)
        if m:
            jid = int(m.group(1))
            jobs[jid] = {"kind": m.group(2), "segs": int(m.group(4)), "prev": m.group(6),
                         "prev_id": int(m.group(7)) if m.group(7) else None, "final": m.group(8)}
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
        if first and pgm == PGM and orig == ORIG:
            found.append((t, job, seg))
    if not jobs or not n_lines:
        return ["verdict: eligibility unverified (no job or segment identity in this journal)"]
    out = []
    direct = exposed = buffers = 0
    for t, job, seg in found:
        sg = segs.get((job, seg))
        if sg is None or sg[1] != title or job not in jobs:
            continue
        buffers += 1
        prefix, _, pud0 = sg
        j = jobs[job]
        ok = seg == 0 and j["prev"] == "acb"
        direct += ok
        inh = inherited(jobs, job) if ok else "-"
        exp = ok and inh not in ("UNKNOWN", "dcb", "-") and int(inh, 16) != WANT
        exposed += exp
        out.append("buffer t %.2f job %d seg %d/%d previous job %s, prefix %d dwords, prefix ud0 %s, inherited %s: %s"
                   % (t, job, seg, j["segs"], j["prev"], prefix, pud0, inh, "EXPOSED" if exp else ("DIRECT" if ok else "not direct")))
    out.append("buffers %d, direct %d, exposed %d" % (buffers, direct, exposed))
    return out


if __name__ == "__main__":
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 12673
    with open(sys.argv[1], errors="replace") as f:
        print("\n".join(report(f, size)))
