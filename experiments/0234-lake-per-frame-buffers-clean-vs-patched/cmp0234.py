#!/usr/bin/env python3
# BC5 experiment 0234: the night lake's water constants in clean and patched frames.
# The water's draws (PS 0x11d01ff900, four per frame) take a pointer to their constants at user-data dwords 28-29 of
# each stage (draw journal "bake ud" lines). Per frame the title allocates them from a pool of 128-KiB blocks
# (0x11e02c0000-0x11e0d8ffff in N3), always at the same offsets in the block: draw k (k = 0..3 in journal order) has its
# pixel-stage constants at 0xc554 - k*0x308 (0x280 bytes) and its vertex-stage constants 0x280 above (0x88 bytes).
# Exp 0212's dump ranges hold that slot of two blocks: 0x11e04c0000 + 0x20000 (block 0x11e04c0000) and
# 0x11e0c2b000 + 0x2000 (block 0x11e0c20000 at +0xb000). So each dump has the water constants of the last frame that
# used that block (the hashes show both ranges rewritten nearly every second).
#  dumps <run dir> <bench.txt>: shots classed by the bench's patch share (clean < 5 %, patched >= 8 %, others left out);
#      per draw, stage and dword: constant in all samples, separating (no value shared between the classes, and one
#      class with a single value or both with at most two), or varying. Separating dwords are listed with their values
#      (at most 3 per class); the rest only as counts. With MINSIM=<percent> only the samples whose dwords match the
#      most common value at that place for at least that share are kept: the slot holds the water's constants only
#      in the frames whose allocation layout put them there.
#  journal <direct.log>: per journalled water draw, journal time (last "t <s>" seen), the render target and the
#      vertex stage's slot-4 image (dynamic resolution), in wall clock (file mtime minus (last t - t), +-1 s).
# Runs on the box (the dumps are the title's memory); prints summaries only.
import collections, datetime, glob, os, re, struct, sys

DRAWS = 4
PS_OFF, GS_OFF, STEP, PS_LEN, GS_LEN = 0xc554, 0xc554 + 0x280, 0x308, 0x280, 0x88
RANGES = {"11e04c0000": 0x0, "11e0c2b000": -0xb000}  # dump file base -> (block offset to file offset)


def regions(path, base):
    data = open(path, "rb").read()
    out = {}
    for k in range(DRAWS):
        for st, off, ln in (("ps", PS_OFF - k * STEP, PS_LEN), ("gs", GS_OFF - k * STEP, GS_LEN)):
            o = off + RANGES[base]
            out[(k, st)] = struct.unpack_from("<%dI" % (ln // 4), data, o)
    return out


def f32(v):
    x = struct.unpack("<f", struct.pack("<I", v))[0]
    return "%.6g" % x if 1e-6 < abs(x) < 1e7 or x == 0 else "-"


def dumps(rd, bench):
    share = {}
    for l in open(bench):
        m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
        if m:
            share[m[2]] = float(m[3])
    cls = {ts: ("clean" if p < 5 else "patched") for ts, p in share.items() if p < 5 or p >= 8}
    samples = []  # (ts, class, base, regions)
    for ts, c in sorted(cls.items()):
        for base in RANGES:
            p = os.path.join(rd, "dumps", "%s.%s.bin" % (ts, base))
            if os.path.exists(p):
                samples.append((ts, c, base, regions(p, base)))
    print("# %s: %d shots classed (%s), %d samples" % (
        rd, len(cls), ", ".join("%s %s" % (k, v) for k, v in sorted(collections.Counter(cls.values()).items())),
        len(samples)))
    print("  clean: %s" % " ".join(ts for ts, c in sorted(cls.items()) if c == "clean"))
    print("  patched: %s" % " ".join(ts for ts, c in sorted(cls.items()) if c == "patched"))
    # how alike the samples are: per sample, the share of dwords equal to the most common value at that place
    mode = {}
    for key in samples[0][3]:
        for i in range(len(samples[0][3][key])):
            mode[(key, i)] = collections.Counter(s[3][key][i] for s in samples).most_common(1)[0][0]
    sim = {}
    for ts, c, base, r in samples:
        sim[(ts, base)] = round(100 * sum(r[key][i] == mode[(key, i)] for key in r
                                          for i in range(len(r[key]))) / len(mode))
    print("  per sample, dwords equal to the most common value: " + " ".join(
        "%s/%s:%d%%" % (ts, base[-5:], sim[(ts, base)]) for ts, c, base, r in samples))
    # MINSIM=<percent>: keep only the samples that look like the water's constants (the slot is used for other data
    # in the other frames that took the block)
    minsim = int(os.environ.get("MINSIM", "0"))
    if minsim:
        samples = [s for s in samples if sim[(s[0], s[2])] >= minsim]
        print("  MINSIM %d: kept %s" % (minsim, " ".join("%s/%s(%s)" % (s[0], s[2][-5:], s[1][0]) for s in samples)))
    tot = collections.Counter()
    sep = []
    var = collections.defaultdict(list)
    for key in samples[0][3]:
        for i in range(len(samples[0][3][key])):
            vc = {s[3][key][i] for s in samples if s[1] == "clean"}
            vp = {s[3][key][i] for s in samples if s[1] == "patched"}
            if len(vc | vp) == 1:
                tot["constant"] += 1
            elif vc and vp and not (vc & vp) and (len(vc) == 1 or len(vp) == 1 or len(vc) + len(vp) <= 4):
                tot["separating"] += 1
                sep.append((key, i, sorted(vc), sorted(vp)))
            else:
                tot["varying"] += 1
                var[key].append(i)
    print("  dwords: %s" % ", ".join("%s %d" % kv for kv in sorted(tot.items())))
    for key in sorted(var):
        print("  varying in draw %d %s: dwords %s" % (key[0], key[1], spans(var[key])))
    for (k, st), i, vc, vp in sep:
        print("  SEPARATING draw %d %s dword %d (+0x%x): clean %s | patched %s" % (
            k, st, i, i * 4, ", ".join("%08x (%s)" % (v, f32(v)) for v in vc[:3]) + (" +%d" % (len(vc) - 3) if len(vc) > 3 else ""),
            ", ".join("%08x (%s)" % (v, f32(v)) for v in vp[:3]) + (" +%d" % (len(vp) - 3) if len(vp) > 3 else "")))


def spans(ix):
    out, a = [], None
    for j, i in enumerate(ix):
        if a is None:
            a = i
        if j + 1 == len(ix) or ix[j + 1] != i + 1:
            out.append(str(a) if a == i else "%d-%d" % (a, i))
            a = None
    return " ".join(out)


def journal(path):
    T = re.compile(r"\bt (\d+\.\d+)")
    DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| rt0 (\S+) (\d+x\d+) .*\| ps (\S+) ")
    UD = re.compile(r"^bake ud (ps|gs|es|vs) buf (\d+) at (\d+): (.*)$")
    t, owner, rows = 0.0, {}, []
    for line in open(path, errors="replace"):
        if line.startswith("timing: t ") or line.startswith("frame profile: t "):
            m = T.search(line)
            if m:
                t = float(m[1])
            continue
        m = DRAW.match(line)
        if m:
            if m[5].lower() == "11d01ff900":
                owner[(m[1], m[2])] = (t, m[3], m[4])
            continue
        m = UD.match(line)
        if m and m[1] == "gs" and (m[2], m[3]) in owner:
            d = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
            d1, d2 = d[17], d[18]
            w, h = ((d2 & 0xfff) << 2 | d1 >> 30) + 1, ((d2 >> 14) & 0x3fff) + 1
            rows.append(owner[(m[2], m[3])] + ("%dx%d" % (w, h),))
    end = os.path.getmtime(path)
    last = t
    print("# %s: %d water draws journalled; wall = mtime %s - (last t %.1f - t)" % (
        path, len(rows), datetime.datetime.fromtimestamp(end).strftime("%H:%M:%S"), last))
    print("  wall      t        rt0 base     rt0 size   gs slot-4 image")
    prev = None
    for t, rt, sz, img in rows:
        key = (round(t, 1), rt, sz, img)
        if key == prev:
            continue
        prev = key
        print("  %s %8.1f  %s %-10s %s" % (
            datetime.datetime.fromtimestamp(end - (last - t)).strftime("%H:%M:%S"), t, rt, sz, img))


if __name__ == "__main__":
    if sys.argv[1] == "dumps":
        dumps(sys.argv[2], sys.argv[3])
    else:
        journal(sys.argv[2])
