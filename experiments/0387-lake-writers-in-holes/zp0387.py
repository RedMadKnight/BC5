#!/usr/bin/env python3
"""BC5 experiment 0387: which lake writer loses the cells. Standard library only; run after the run, on the box.
usage: zp0387.py <zpass.dat> <zpass.dat.meta> <tag>.tz.txt <tag>.snaps.txt
A record is 16 bytes per RB: begin at +0, end at +8, each with bit 63 set once written (radv_query.c:215-225, Mesa ab2374a).
Writers are keyed by pixel shader and their order within the job. A job's share for a writer is its passed samples over the
job's total, so render size falls out. Only jobs with MIN_WRITERS or more writers count: those are the frame's lake jobs.
Labels come from the depth: each final of the poller's captures is joined to the nearest lake job within JOIN_MS by the
monotonic clock, both sides being CLOCK_MONOTONIC, and a final with no such job is left out as unknown (LESSONS R11). A hole
frame has a hole share of HOLE or more, a clean frame under CLEAN.
The rule, fixed before the run: with MIN_FRAMES or more of each, a writer loses cells if its median share in hole frames is at most
LOST of its median share in clean frames, and its clean share is at least MIN_SHARE. TODO(verify): gfx1013's RB count; records
hold 256 bytes, so unused RBs stay zero and are ignored."""
import re, statistics, struct, sys

RB = 16
VALID = 1 << 63
MIN_WRITERS, JOIN_MS, HOLE, CLEAN, MIN_FRAMES, LOST, MIN_SHARE = 20, 40.0, 0.05, 0.01, 10, 0.8, 0.001


def record(raw):
    """(passed samples, begin written, end written)."""
    total, begins, ends = 0, 0, 0
    for r in range(RB):
        b, e = struct.unpack_from("<QQ", raw, r * 16)
        begins += 1 if b & VALID else 0
        ends += 1 if e & VALID else 0
        if b & VALID and e & VALID:
            total += (e & ~VALID) - (b & ~VALID)
    return total, begins > 0, ends > 0


def jobs_of(data, meta):
    """{job: {"ms", "keys": {(ps, order): passed}}} and the number of records never begun."""
    jobs, skipped = {}, 0
    for line in meta.splitlines():
        rec, job, ps, _op, _cond, ms = line.split()
        rec = int(rec)
        raw = data[rec * 256:(rec + 1) * 256]
        if len(raw) != 256:
            continue
        passed, began, ended = record(raw)
        j = jobs.setdefault(job, {"ms": float(ms), "keys": {}, "n": 0})
        order = j["n"]
        j["n"] += 1
        if not began:
            skipped += 1
        if began and ended:
            j["keys"][(ps, order)] = passed
    return jobs, skipped


def finals_of(tz, snaps):
    """[(final, ms, hole share)] from tz's lines and the frames' monotonic starts."""
    mono = dict((f"{m[0]}.{m[1]}", float(m[2]) * 1000) for m in re.findall(r"^(c\d+) (f\d+) frame mono ([0-9.]+)", snaps, re.M))
    out = []
    for name, holes in re.findall(r"^\s+(c\d+\.f\d+) w \d+ holes ([0-9.]+)", tz, re.M):
        if name in mono:
            out.append((name, mono[name], float(holes)))
    return out


def label(jobs, finals):
    """{job: hole share}: each final to its nearest lake job within JOIN_MS."""
    lake = sorted((j["ms"], k) for k, j in jobs.items() if j["n"] >= MIN_WRITERS)
    out = {}
    for _name, ms, holes in finals:
        best = min(lake, key=lambda x: abs(x[0] - ms), default=None)
        if best is not None and abs(best[0] - ms) <= JOIN_MS:
            out[best[1]] = holes
    return out


def shares(jobs, names):
    out = {}
    for name in names:
        j = jobs[name]
        total = sum(j["keys"].values())
        if total:
            for k, v in j["keys"].items():
                out.setdefault(k, []).append(v / total)
    return out


def summarise(data, meta, tz, snaps):
    jobs, skipped = jobs_of(data, meta)
    lake = [k for k, j in jobs.items() if j["n"] >= MIN_WRITERS]
    finals = finals_of(tz, snaps)
    labels = label(jobs, finals)
    hole = [k for k, h in labels.items() if h >= HOLE]
    clean = [k for k, h in labels.items() if h < CLEAN]
    out = [f"# {len(jobs)} jobs, {len(lake)} lake jobs, {skipped} records skipped by the CP; {len(finals)} finals, {len(labels)} joined, {len(hole)} hole, {len(clean)} clean"]
    if len(hole) < MIN_FRAMES or len(clean) < MIN_FRAMES:
        out.append(f"# NO TEST: fewer than {MIN_FRAMES} hole or clean frames")
    else:
        sh, sc = shares(jobs, hole), shares(jobs, clean)
        rows = []
        for k, v in sc.items():
            c = statistics.median(v)
            h = statistics.median(sh[k]) if k in sh else 0.0
            if c >= MIN_SHARE:
                rows.append((h / c, k, c, h, len(sh.get(k, [])), len(v)))
        rows.sort(key=lambda r: r[0])
        lost = [r for r in rows if r[0] <= LOST]
        out.append(f"# {len(lost)} of {len(rows)} writers lose cells: hole share at most {LOST} of clean")
        for r, k, c, h, nh, nc in rows[:25]:
            out.append(f"ratio {r:.3f} ps {k[0]} order {k[1]} clean {c:.5f} ({nc}) hole {h:.5f} ({nh})")
    # With no clean frames the two hole halves still swing against each other: the widest shares, labels or not.
    swing = []
    for k, v in shares(jobs, lake).items():
        if len(v) >= 20:
            v = sorted(v)
            lo, mid, hi = v[len(v) // 10], v[len(v) // 2], v[len(v) * 9 // 10]
            if mid >= MIN_SHARE:
                swing.append(((hi - lo) / mid, k, lo, mid, hi, len(v)))
    swing.sort(key=lambda r: r[0], reverse=True)
    out.append(f"# the widest shares across {len(lake)} lake jobs")
    for w, k, lo, mid, hi, n in swing[:25]:
        out.append(f"swing {w:.3f} ps {k[0]} order {k[1]} share {lo:.5f} {mid:.5f} {hi:.5f} ({n})")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(newline=chr(10))
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    def text(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    sys.stdout.write(summarise(data, text(sys.argv[2]), text(sys.argv[3]), text(sys.argv[4])))
