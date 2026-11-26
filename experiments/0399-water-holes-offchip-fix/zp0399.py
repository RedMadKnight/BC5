#!/usr/bin/env python3
"""BC5 experiment 0399: which lake writers differ between the two hole sets. Standard library only; run after the run, on the box.
usage: zp0399.py <zpass.dat> <zpass.dat.meta> <tag>.tz.txt <tag>.snaps.txt <tag>.jobs.tsv.gz [K4.zp.txt]
A record is 16 bytes per RB: begin at +0, end at +8, each with bit 63 set once written (radv_query.c:215-225, Mesa ab2374a).
Writers are keyed by pixel shader and its occurrence within the job (F772: the order in the job shifts between layouts). A job's
share for a writer is its passed samples over the job's total, so render size falls out; a writer missing from a job counts 0
there. A job with MIN_WRITERS or more writers is the frame's lake job. The small jobs around it write the same depth (K7: 1, 108, 3 and 9
writers a frame), so a frame's group runs from the job before its lake job to the job before the next one, and a key also holds the
job's place in that group: 0 is the lake job. Exp 0387's reader left the small jobs out.
Each final is joined to the nearest lake job within JOIN_MS by the monotonic clock, both sides being CLOCK_MONOTONIC, and a final
with no such job is left out as unknown (LESSONS R11). The clock cannot tell which of two neighbouring jobs drew a frame, and a
frame off by one reads as a coin (F485), so every result is taken at each lag in LAGS and the one with the most writers named is
used, a tie going to the lowest ratio. Shares are compared by their means: a writer with two levels gives a median that flips with
any small majority, so medians named it at every lag, and means do not (the reader's own test).
Labels: tz's side of each final, A or B (F342's two sets), and its hole share: a hole frame HOLE or more, a clean frame under CLEAN.
The rules, fixed before the run, with MIN_FRAMES or more of each group:
  a writer follows the side if its mean share in one side is at most LOST of the other's, the larger being MIN_SHARE or more;
  a writer loses cells if its mean share in hole frames is at most LOST of clean frames', the clean one MIN_SHARE or more;
  an RB follows the side by the same LOST on its share of the job's passed samples;
  a writer follows the hole share if, over MIN_SPREAD or more hole frames of the commonest width, the rank correlation of its share with
  the frame's hole share is RHO or less, its mean share being MIN_SHARE or more. This is the test for a writer that draws both sets: X
  and Y are about the same size, so it loses as much on either side and no comparison of the sides can see it.
K4's catcher ran on clean frames, so its table is a possible clean reference: over the main layout's writers from order REF_ORDER on,
the ones only the lake job has, each writer's share in this run's hole frames against K4's, with the same LOST. It reads only if this
run's lake job has K4's writer count, and K7's did not (108 against 146, F774). It is another run: what it names is a lead.
TODO(verify): gfx1013's RB count; records hold 256 bytes, so unused RBs stay zero and are ignored; the reader prints the count."""
import bisect, collections, gzip, re, struct, sys

RB = 16
VALID = 1 << 63
MIN_WRITERS, JOIN_MS, HOLE, CLEAN, MIN_FRAMES, LOST, MIN_SHARE = 20, 40.0, 0.05, 0.01, 10, 0.8, 0.001
LAGS = (0, -1, 1, -2, 2)   # a tie goes to the earlier one
REF_ORDER = 9
MIN_SPREAD, RHO = 30, -0.5


def record(raw):
    """(passed samples by RB, mask of the RBs whose begin was written, any end written)."""
    passed, begins, ends = [0] * RB, 0, 0
    for r in range(RB):
        b, e = struct.unpack_from("<QQ", raw, r * 16)
        begins |= (1 << r) if b & VALID else 0
        ends += 1 if e & VALID else 0
        if b & VALID and e & VALID:
            passed[r] = (e & ~VALID) - (b & ~VALID)
    return passed, begins, ends > 0


def jobs_of(data, meta):
    """{job: {"ms", "n", "keys": {(ps, occurrence): passed}, "rb": [passed]}}, the records never begun, the mask of RBs seen."""
    jobs, skipped, seen = {}, 0, 0
    for line in meta.splitlines():
        rec, job, ps, _op, _cond, ms = line.split()
        rec = int(rec)
        raw = data[rec * 256:(rec + 1) * 256]
        if len(raw) != 256:
            continue
        passed, began, ended = record(raw)
        j = jobs.setdefault(job, {"ms": float(ms), "keys": {}, "n": 0, "of": {}, "rb": [0] * RB, "seq": []})
        j["seq"].append((ps, sum(passed)))
        occ = j["of"].get(ps, 0)
        j["of"][ps] = occ + 1
        j["n"] += 1
        seen |= began
        if not began:
            skipped += 1
        if began and ended:
            j["keys"][(ps, occ)] = sum(passed)
            for r, p in enumerate(passed):
                j["rb"][r] += p
    return jobs, skipped, seen


def frames_of(jobs):
    """{lake job: its frame's group}, one pseudo job per frame with keys (shader, occurrence, place in the group)."""
    order = sorted(jobs, key=lambda k: jobs[k]["ms"])
    marks = [i for i, k in enumerate(order) if jobs[k]["n"] >= MIN_WRITERS]
    lakes = set(marks)
    out = {}
    for m, i in enumerate(marks):
        start = i if i == 0 or i - 1 in lakes else i - 1
        end = max(i + 1, marks[m + 1] - 1) if m + 1 < len(marks) else len(order)
        g = {"ms": jobs[order[i]]["ms"], "keys": {}, "n": 0, "rb": [0] * RB, "seq": jobs[order[i]]["seq"]}
        for at in range(start, end):
            j = jobs[order[at]]
            g["n"] += j["n"]
            for (ps, occ), v in j["keys"].items():
                g["keys"][(ps, occ, at - i)] = v
            for r, p in enumerate(j["rb"]):
                g["rb"][r] += p
        out[order[i]] = g
    return out


def finals_of(tz, snaps):
    """[{"name", "ms", "w", "holes", "side"}] from tz's lines and the frames' monotonic starts."""
    mono = dict((f"{m[0]}.{m[1]}", float(m[2]) * 1000) for m in re.findall(r"^(c\d+) (f\d+) frame mono ([0-9.]+)", snaps, re.M))
    side = dict(re.findall(r"^side (c\d+\.f\d+) (\S)", tz, re.M))
    out = []
    for name, w, holes in re.findall(r"^\s+(c\d+\.f\d+) w (\d+) holes ([0-9.]+)", tz, re.M):
        if name in mono:
            out.append({"name": name, "ms": mono[name], "w": int(w), "holes": float(holes), "side": side.get(name, "?")})
    return out


def label(jobs, finals):
    """({lag: {job: final}}, finals joined): each final to its nearest lake job within JOIN_MS, then to the jobs beside that one."""
    lake = sorted((j["ms"], k) for k, j in jobs.items() if j["n"] >= MIN_WRITERS)
    times = [t for t, _ in lake]
    out, joined = {lag: {} for lag in LAGS}, 0
    for f in finals:
        i = bisect.bisect_left(times, f["ms"])
        near = [n for n in (i - 1, i) if 0 <= n < len(times)]
        if not near:
            continue
        n = min(near, key=lambda x: abs(times[x] - f["ms"]))
        if abs(times[n] - f["ms"]) > JOIN_MS:
            continue
        joined += 1
        for lag in LAGS:
            if 0 <= n + lag < len(lake):
                out[lag][lake[n + lag][1]] = f
    return out, joined


def means(jobs, names):
    """({key: mean share, 0 where a job lacks it}, jobs counted)."""
    rows = [j for j in (jobs[n] for n in names) if sum(j["keys"].values())]
    seen = {}
    for j in rows:
        total = sum(j["keys"].values())
        for k, v in j["keys"].items():
            seen[k] = seen.get(k, 0.0) + v / total
    return {k: v / len(rows) for k, v in seen.items()}, len(rows)


def by_side(jobs, a, b):
    """[(smaller over larger, the side with less, key, share A, share B)], lowest first."""
    ma, na = means(jobs, a)
    mb, nb = means(jobs, b)
    rows = []
    if na >= MIN_FRAMES and nb >= MIN_FRAMES:
        for k in set(ma) | set(mb):
            x, y = ma.get(k, 0.0), mb.get(k, 0.0)
            if max(x, y) >= MIN_SHARE:
                rows.append((min(x, y) / max(x, y), "A" if x < y else "B", k, x, y))
    return sorted(rows, key=lambda r: (r[0], r[2]))


def by_holes(jobs, hole, clean):
    """[(hole over clean, key, clean share, hole share)], lowest first."""
    mh, nh = means(jobs, hole)
    mc, nc = means(jobs, clean)
    rows = []
    if nh >= MIN_FRAMES and nc >= MIN_FRAMES:
        rows = [(mh.get(k, 0.0) / c, k, c, mh.get(k, 0.0)) for k, c in mc.items() if c >= MIN_SHARE]
    return sorted(rows, key=lambda r: (r[0], r[1]))


def rb_shares(jobs, names, rbs):
    out = {}
    rows = [j["rb"] for j in (jobs[n] for n in names) if sum(j["rb"])]
    for r in rbs:
        out[r] = sum(x[r] / sum(x) for x in rows) / len(rows) if rows else None
    return out


def reference(text):
    """{order: (shader, median passed)} of K4's main layout from REF_ORDER on, and that layout's writer count."""
    rows = re.findall(r"^\s*(\d+) ps (\S+) op \S+ in_cond \d+ frames (\d+) skipped \d+ passed \d+ (\d+) \d+", text, re.M)
    top = max((int(r[2]) for r in rows), default=0)
    main = [(int(o), ps, int(p)) for o, ps, f, p in rows if int(f) * 2 >= top]
    return {o: (ps, p) for o, ps, p in main if o >= REF_ORDER}, 1 + max((o for o, _, _ in main), default=-1)


def across(jobs, names, ref, count):
    """[(hole share over K4's, order, this run's shader, K4's, K4's share, this run's)], lowest first, or the reason there are none."""
    seqs = [jobs[n]["seq"] for n in names]
    if not ref:
        return "no K4 table"
    if not seqs:
        return "no hole frames"
    n = collections.Counter(len(s) for s in seqs).most_common(1)[0][0]
    use = [s for s in seqs if len(s) == n and sum(s[o][1] for o in ref if o < n)]
    if n != count or len(use) < MIN_FRAMES:
        return f"{len(use)} jobs of {n} writers against K4's {count}"
    total = sum(p for _, p in ref.values())
    rows = []
    for o, (ps, p) in ref.items():
        there = p / total
        here = sum(s[o][1] / sum(s[x][1] for x in ref) for s in use) / len(use)
        if there >= MIN_SHARE:
            rows.append((here / there, o, use[0][o][0], ps, there, here))
    return sorted(rows, key=lambda r: (r[0], r[1]))


def ranks(v):
    """Ranks, ties sharing their mean."""
    order = sorted(range(len(v)), key=v.__getitem__)
    out, i = [0.0] * len(v), 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + j) / 2
        i = j + 1
    return out


def correlation(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx, syy = sum((a - mx) ** 2 for a in x), sum((b - my) ** 2 for b in y)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else 0.0


def by_spread(jobs, labels):
    """[(rank correlation of share with hole share, key, mean share)], lowest first, over hole frames of the commonest width."""
    held = [(k, f) for k, f in labels.items() if f["holes"] >= HOLE and sum(jobs[k]["keys"].values())]
    if not held:
        return []
    width = collections.Counter(f["w"] for _, f in held).most_common(1)[0][0]
    held = [(k, f) for k, f in held if f["w"] == width]
    if len(held) < MIN_SPREAD:
        return []
    holes = ranks([f["holes"] for _, f in held])
    shares = {}
    for at, (k, _) in enumerate(held):
        total = sum(jobs[k]["keys"].values())
        for key, v in jobs[k]["keys"].items():
            shares.setdefault(key, [0.0] * len(held))[at] = v / total
    rows = []
    for key, v in shares.items():
        mean = sum(v) / len(v)
        if mean >= MIN_SHARE:
            rows.append((correlation(ranks(v), holes), key, mean))
    return sorted(rows, key=lambda r: (r[0], r[1]))


def groups(labels):
    """The job names of side A, side B, hole frames and clean frames."""
    a = [k for k, f in labels.items() if f["side"] == "A"]
    b = [k for k, f in labels.items() if f["side"] == "B"]
    hole = [k for k, f in labels.items() if f["holes"] >= HOLE]
    clean = [k for k, f in labels.items() if f["holes"] < CLEAN]
    return a, b, hole, clean


def table(jobs, labels):
    """One line per lake job at any lag of a final: passed samples, so any later reader can start from it."""
    names = sorted({k for lag in LAGS for k in labels[lag]}, key=lambda k: jobs[k]["ms"])
    keys = sorted({k for n in names for k in jobs[n]["keys"]})
    head = ["job", "ms", "final", "w", "holes", "side"] + [f"rb{r}" for r in range(RB)] + [f"{w}:{p}.{o}" for p, o, w in keys]
    rows = ["\t".join(head)]
    for n in names:
        j, f = jobs[n], labels[0].get(n)
        left = [n, f"{j['ms']:.3f}"] + ([f["name"], str(f["w"]), f"{f['holes']:.3f}", f["side"]] if f else ["-", "-", "-", "-"])
        rows.append("\t".join(left + [str(x) for x in j["rb"]] + [str(j["keys"].get(k, 0)) for k in keys]))
    return "\n".join(rows) + "\n"


def summarise(data, meta, tz, snaps, k4=""):
    """(the text, the jobs table)."""
    raw, skipped, seen = jobs_of(data, meta)
    jobs = frames_of(raw)
    lake = list(jobs)
    finals = finals_of(tz, snaps)
    labels, joined = label(jobs, finals)
    rbs = [r for r in range(RB) if seen >> r & 1]
    out = [f"# {len(raw)} jobs, {len(lake)} lake jobs, {skipped} records skipped by the CP, {len(rbs)} RBs with a begin written ({rbs}); {len(finals)} finals, {joined} joined"]
    best, score = LAGS[0], (-1, 0.0)
    for lag in LAGS:
        a, b, hole, clean = groups(labels[lag])
        rs, rh = by_side(jobs, a, b), by_holes(jobs, hole, clean)
        rc = by_spread(jobs, labels[lag])
        s, h, c = sum(r[0] <= LOST for r in rs), sum(r[0] <= LOST for r in rh), sum(r[0] <= RHO for r in rc)
        out.append(f"# lag {lag}: side A {len(a)}, B {len(b)}, hole {len(hole)}, clean {len(clean)}: {s} writers follow the side, {h} lose cells, {c} follow the hole share")
        now = (s + h + c, -min([r[0] for r in rs + rh], default=1.0))
        if now > score:
            best, score = lag, now
    a, b, hole, clean = groups(labels[best])
    out.append(f"# lag used: {best}")
    rows = by_side(jobs, a, b)
    if rows:
        out.append(f"# {sum(r[0] <= LOST for r in rows)} of {len(rows)} writers follow the side: the smaller share at most {LOST} of the larger")
        for r, low, k, x, y in rows:
            out.append(f"side {r:.3f} low {low} ps {k[0]} occ {k[1]} job {k[2]} A {x:.5f} B {y:.5f}")
    else:
        out.append(f"# NO TEST by side: fewer than {MIN_FRAMES} frames of a side")
    rows = by_holes(jobs, hole, clean)
    if rows:
        out.append(f"# {sum(r[0] <= LOST for r in rows)} of {len(rows)} writers lose cells: hole share at most {LOST} of clean")
        for r, k, c, h in rows[:25]:
            out.append(f"ratio {r:.3f} ps {k[0]} occ {k[1]} job {k[2]} clean {c:.5f} hole {h:.5f}")
    else:
        out.append(f"# NO TEST by holes: fewer than {MIN_FRAMES} hole or clean frames")
    rows = by_spread(jobs, labels[best])
    if rows:
        out.append(f"# {sum(r[0] <= RHO for r in rows)} of {len(rows)} writers follow the hole share: rank correlation at most {RHO}")
        for r, k, m in rows[:25]:
            out.append(f"spread {r:.3f} ps {k[0]} occ {k[1]} job {k[2]} mean share {m:.5f}")
    else:
        out.append(f"# NO TEST by hole share: fewer than {MIN_SPREAD} hole frames of one width")
    ref, count = reference(k4)
    rows = across(jobs, hole, ref, count)
    if isinstance(rows, str):
        out.append(f"# NO TEST against K4's clean frames: {rows}")
    else:
        out.append(f"# {sum(r[0] <= LOST for r in rows)} of {len(rows)} writers hold at most {LOST} of their share in K4's clean frames (another run: a lead)")
        for r, o, here, there, x, y in rows[:25]:
            out.append(f"across {r:.3f} order {o} ps {here} K4 ps {there} clean {x:.5f} hole {y:.5f}")
    ra, rb = rb_shares(jobs, a, rbs), rb_shares(jobs, b, rbs)
    test = len(a) >= MIN_FRAMES and len(b) >= MIN_FRAMES
    follow = [r for r in rbs if test and ra[r] is not None and rb[r] is not None and max(ra[r], rb[r]) > 0 and min(ra[r], rb[r]) / max(ra[r], rb[r]) <= LOST]
    out.append(f"# {len(follow)} of {len(rbs)} RBs follow the side" if test else "# NO TEST of the RBs by side")
    for r in rbs:
        x, y = ra[r], rb[r]
        out.append("rb %d A %s B %s" % (r, "-" if x is None else f"{x:.4f}", "-" if y is None else f"{y:.4f}"))
    # With no labels the shares still swing against each other: the widest, a lead only.
    swing, n = [], {}
    for name in lake:
        j = jobs[name]
        total = sum(j["keys"].values())
        for k, v in j["keys"].items():
            if total:
                n.setdefault(k, []).append(v / total)
    for k, v in n.items():
        if len(v) >= 20:
            v = sorted(v)
            lo, mid, hi = v[len(v) // 10], v[len(v) // 2], v[len(v) * 9 // 10]
            if mid >= MIN_SHARE:
                swing.append(((hi - lo) / mid, k, lo, mid, hi, len(v)))
    swing.sort(key=lambda r: (-r[0], r[1]))
    out.append(f"# the widest shares across {len(lake)} lake jobs")
    for w, k, lo, mid, hi, c in swing[:15]:
        out.append(f"swing {w:.3f} ps {k[0]} occ {k[1]} job {k[2]} share {lo:.5f} {mid:.5f} {hi:.5f} ({c})")
    return "\n".join(out) + "\n", table(jobs, labels)


if __name__ == "__main__":
    sys.stdout.reconfigure(newline=chr(10))
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    def text(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    report, jobs_table = summarise(data, text(sys.argv[2]), text(sys.argv[3]), text(sys.argv[4]), text(sys.argv[6]) if len(sys.argv) > 6 else "")
    sys.stdout.write(report)
    with open(sys.argv[5], "wb") as f:
        with gzip.GzipFile(filename="", fileobj=f, mode="wb", mtime=0) as g:
            g.write(jobs_table.encode())
