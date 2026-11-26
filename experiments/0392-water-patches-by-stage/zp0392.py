#!/usr/bin/env python3
"""BC5 experiment 0392: where the water's cells go. Reads the records of lake_probe's zpass, stats and ureg, on the box.
Each frame is a job with the water's first shader in it. A frame's state comes from the water's own samples: S is occurrences 0 and 2
of PS 0x11d01ff900 (F775), TOP the run's 95th percentile of S, and a frame is clean at CLEAN of TOP or more, a hole frame at HOLE or
less. So labels need no depth read and cover the whole run. Prints, per draw of that shader:
  each counter's mean in clean and in hole frames, and their ratio;
then the reading (the README's table): the first stage, in pipeline order, whose count falls by LOST or more in occurrences 0 and 2;
the registers ureg read, and which of them differs between the states; per arm, frames, mean S and the share of hole frames; S against
the depth's hole share at the finals, capture by capture.
usage: zp0392.py <zpass.dat> <zpass.dat.meta> <tag>.tz.txt <tag>.snaps.txt <arms.log> <out frames.tsv.gz>
The frames' table has the job, its time, S, the state, and z, HS, DS, PS for each of the four draws, so a later reader can start there."""
import gzip
import re
import statistics as st
import struct
import sys

RECORD, STAT_END, RB = 256, 128, 16
WATER = "0x11d01ff900"
CLEAN, HOLE, LOST, MIN_FRAMES = 0.97, 0.90, 0.95, 10
# Mesa ab2374a radv_query.c:388, through VkQueryPipelineStatisticFlagBits' order: IA_VERTICES is qword 7, IA_PRIMITIVES 6, VS 3, GS 4,
# GS_PRIMITIVES 5, C_INVOCATIONS 2, C_PRIMITIVES 1, PS 0, HS 8, DS 9, CS 10.
NAMES = ("PS", "C_PRIM", "C_INV", "VS", "GS", "GS_PRIM", "IA_PRIM", "IA_VERT", "HS", "DS", "CS")
STAGES = ("IA_VERT", "IA_PRIM", "HS", "DS", "VS", "GS", "GS_PRIM", "C_INV", "C_PRIM", "PS")
UREGS = ("VGT_TF_RING_SIZE", "VGT_HS_OFFCHIP_PARAM", "VGT_TF_MEMORY_BASE", "VGT_TF_MEMORY_BASE_HI", "GE_CNTL", "GE_PC_ALLOC")
VALID = 1 << 63


def samples(raw):
    """Passed samples of one z record, or None if a begin or an end of a written RB is missing."""
    out, seen = 0, 0
    for r in range(RB):
        b, e = struct.unpack_from("<QQ", raw, r * 16)
        if not b & VALID and not e & VALID:
            continue
        if not b & VALID or not e & VALID:
            return None
        seen += 1
        out += (e & ~VALID) - (b & ~VALID)
    return out if seen else None


def stats(raw):
    """{counter: end - begin} of one s record, or None if a counter wasn't written."""
    out = {}
    for k, name in enumerate(NAMES):
        b, e = struct.unpack_from("<Q", raw, k * 8)[0], struct.unpack_from("<Q", raw, STAT_END + k * 8)[0]
        if not b & VALID or not e & VALID:
            return None
        out[name] = (e & ~VALID) - (b & ~VALID)
    return out


def frames_of(data, meta):
    """[{"job", "ms", "z": {occ: n}, "s": {occ: {counter: n}}, "u": [...]}] by time; other water shaders' records in "others"."""
    jobs, occ = {}, {}
    bad = 0
    for line in meta.splitlines():
        w = line.split()
        if len(w) != 7:
            continue
        at, job, ps, _op, _cond, ms, kind = int(w[0]), w[1], w[2], w[3], w[4], float(w[5]), w[6]
        j = jobs.setdefault(job, {"job": job, "ms": ms, "z": {}, "s": {}, "u": None, "others": 0})
        if kind == "i":
            continue
        raw = data[at * RECORD:(at + 1) * RECORD]
        if len(raw) < RECORD:
            bad += 1
            continue
        if ps != WATER:
            if kind == "z":
                n = samples(raw)
                j["others"] += n or 0
            continue
        n = occ.get((job, kind), 0)
        occ[(job, kind)] = n + 1
        if kind == "z":
            v = samples(raw)
            if v is None:
                bad += 1
            else:
                j["z"][n] = v
        elif kind == "s":
            v = stats(raw)
            if v is None:
                bad += 1
            else:
                j["s"][n] = v
        elif kind == "u":
            j["u"] = struct.unpack_from(f"<{len(UREGS)}I", raw, 0)
    return sorted((j for j in jobs.values() if 0 in j["z"] and 2 in j["z"]), key=lambda j: j["ms"]), bad


def label(frames):
    s = sorted(f["z"][0] + f["z"][2] for f in frames)
    top = s[int(0.95 * (len(s) - 1))] if s else 0
    for f in frames:
        f["S"] = f["z"][0] + f["z"][2]
        f["state"] = "clean" if f["S"] >= CLEAN * top else "hole" if f["S"] <= HOLE * top else "between"
    return top


def by_counter(frames):
    """[(occ, name, clean mean, hole mean)]; only frames that have that draw's record."""
    rows = []
    for o in range(4):
        for name in ("z",) + STAGES:
            def get(f):
                if name == "z":
                    return f["z"].get(o)
                return f["s"].get(o, {}).get(name)
            c = [get(f) for f in frames if f["state"] == "clean" and get(f) is not None]
            h = [get(f) for f in frames if f["state"] == "hole" and get(f) is not None]
            if len(c) >= MIN_FRAMES and len(h) >= MIN_FRAMES:
                rows.append((o, name, st.mean(c), st.mean(h)))
    return rows


def stage_of(rows):
    """The README's reading, for the two draws that lose: the first stage in pipeline order that falls by LOST or more in either."""
    ratio = {(o, n): (h / c if c else 1.0) for o, n, c, h in rows}
    if not ratio:
        return "NO TEST: too few clean or hole frames"
    for name in STAGES:
        hit = [o for o in (0, 2) if ratio.get((o, name), 1.0) <= LOST]
        if hit:
            return f"first stage to fall: {name} (occurrence {', '.join(map(str, hit))})"
    if any(ratio.get((o, "z"), 1.0) <= LOST for o in (0, 2)):
        return "no counter falls but the samples do: the depth test takes them"
    return "nothing falls"


def registers(frames):
    out = []
    for k, name in enumerate(UREGS):
        seen = {}
        for f in frames:
            if f["u"] is not None:
                seen.setdefault(f["u"][k], {"clean": 0, "hole": 0, "between": 0})[f["state"]] += 1
        for v, c in sorted(seen.items()):
            out.append(f"reg {name} 0x{v:x}: clean {c['clean']} hole {c['hole']} between {c['between']}")
    return out


def to_mono(snaps):
    """(wall, mono) pairs, to put the arm log's wall seconds on the records' clock."""
    p = re.findall(r"wall ([0-9.]+) mono ([0-9.]+)", snaps)
    if not p:
        return None
    return st.median(float(w) - float(m) for w, m in p)


def by_arm(frames, arms, offset, top):
    rows = []
    marks = []
    for line in arms.splitlines():
        w = line.split(None, 2)
        if len(w) >= 2:
            marks.append((int(w[0]), float(w[1]), w[2] if len(w) > 2 else ""))
    for k, (first, wall, text) in enumerate(marks):
        end = marks[k + 1][1] if k + 1 < len(marks) else float("inf")
        g = [f for f in frames if wall <= f["ms"] / 1000 + offset < end]
        keep = " ".join(x for x in text.split() if x not in ("census=1", "zpass=1", "zwater=1", "stats=1", "ureg=1", "inputs=1")) or "off"
        if g:
            rows.append(f"arm {first:2d} frames {len(g):4d} S {st.mean(f['S'] for f in g) / (top or 1):.3f} hole {sum(f['state'] == 'hole' for f in g) / len(g):.3f} | {keep}")
        else:
            rows.append(f"arm {first:2d} frames    0 | {keep}")
    return rows


def against_depth(frames, tz, snaps, window=800128):
    mono = dict((f"{m[0]}.{m[1]}", float(m[2]) * 1000) for m in re.findall(r"^(c\d+) (f\d+) frame mono ([0-9.]+)", snaps, re.M))
    pairs = []
    times = [f["ms"] for f in frames]
    import bisect
    for name, w, holes in re.findall(r"^\s+(c\d+\.f\d+) w (\d+) holes ([0-9.]+)", tz, re.M):
        if name not in mono or w != "2560":
            continue
        i = bisect.bisect_left(times, mono[name])
        near = [k for k in (i - 1, i) if 0 <= k < len(frames)]
        if near:
            k = min(near, key=lambda x: abs(times[x] - mono[name]))
            if abs(times[k] - mono[name]) <= 40:
                pairs.append((float(holes) * window, frames[k]["S"]))
    if len(pairs) < MIN_FRAMES:
        return [f"# against the depth: {len(pairs)} finals joined, NO TEST"]
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = st.mean(x), st.mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    d = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5
    sxx = sum((a - mx) ** 2 for a in x)
    return [f"# against the depth: {len(pairs)} finals at 2560, S against hole pixels r {sxy / d if d else 0:+.2f} slope {sxy / sxx if sxx else 0:+.2f}"]


def table(frames):
    head = ["job", "ms", "S", "state"] + [f"{n}{o}" for o in range(4) for n in ("z", "HS", "DS", "PS")]
    rows = ["\t".join(head)]
    for f in frames:
        left = [f["job"], f"{f['ms']:.3f}", str(f["S"]), f["state"]]
        for o in range(4):
            s = f["s"].get(o, {})
            left += [str(f["z"].get(o, "")), str(s.get("HS", "")), str(s.get("DS", "")), str(s.get("PS", ""))]
        rows.append("\t".join(left))
    return "\n".join(rows) + "\n"


def summarise(data, meta, tz, snaps, arms):
    frames, bad = frames_of(data, meta)
    top = label(frames)
    n = {k: sum(f["state"] == k for f in frames) for k in ("clean", "hole", "between")}
    out = [f"# {len(frames)} frames, {bad} unreadable records; TOP {top}; clean {n['clean']}, hole {n['hole']}, between {n['between']}"]
    rows = by_counter(frames)
    out.append("# " + stage_of(rows))
    for o, name, c, h in rows:
        out.append(f"occ {o} {name:<8} clean {c:>12,.0f} hole {h:>12,.0f} ratio {h / c if c else 0:.3f}")
    out += registers(frames)
    offset = to_mono(snaps)
    out += by_arm(frames, arms, offset, top) if offset is not None else ["# no clock pairs: no arm table"]
    out += against_depth(frames, tz, snaps)
    return "\n".join(out) + "\n", table(frames)


def main():
    a = sys.argv[1:]
    with open(a[0], "rb") as f:
        data = f.read()
    texts = []
    for p in a[1:5]:
        with open(p, encoding="utf-8", errors="replace") as f:
            texts.append(f.read())
    text, tsv = summarise(data, texts[0], texts[1], texts[2], texts[3])
    sys.stdout.write(text)
    with gzip.open(a[5], "wt") as f:
        f.write(tsv)


if __name__ == "__main__":
    main()
