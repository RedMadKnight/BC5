#!/usr/bin/env python3
"""BC5 experiment 0389: the reading made after the runs, from raw/ only. Not part of the plan: the plan's reader is zp0389.py.

N2 was the first run with hole and clean frames, and its holes changed over seconds, not per frame, so the lag rule could not separate
anything. This reads the named shader's four draws in the small job after the lake job at 2560 wide, in frames where that job
sits once at place 2, so a frame group that holds two of them or none can't pass as a change of a draw:
capture by capture against the hole pixels, their levels, a per-frame test, the pattern labels, and the colour metric against the depth
over time.

Usage: after0389.py > raw/after0389.txt
"""
import gzip
import os
import re
import statistics as st

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
WINDOW = 800128  # zp0389's window at 2560 wide: 2128 x 376, sn0389's X0..Y1 cut to whole tiles
PS = "0x11d01ff900"


def text(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return f.read()


def pearson(a, b):
    ma, mb = st.mean(a), st.mean(b)
    n = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    d = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return n / d if d else 0.0


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def slope(x, y):
    mx, my = st.mean(x), st.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x)


def load(tag):
    with gzip.open(os.path.join(RAW, tag + ".jobs.tsv.gz"), "rt") as f:
        rows = [l.rstrip("\n").split("\t") for l in f]
    head, body = rows[0], rows[1:]
    places = {}
    for i, h in enumerate(head):
        if ":" in h:
            place, key = h.split(":")
            ps, occ = key.split(".")
            if ps == PS:
                places.setdefault(int(place), {})[int(occ)] = i
    rb = [i for i, h in enumerate(head) if h.startswith("rb")]
    finals = [r for r in body if r[2] != "-" and r[3] == "2560"]
    good = [r for r in finals if [p for p, c in places.items() if int(r[c[3]]) > 0] == [2]]
    return finals, good, places[2], rb


def draws(tag):
    finals, good, col, rb = load(tag)
    print(f"== {tag}: {len(finals)} finals at 2560, {len(good)} with the small job once at place 2")
    hp = [float(r[4]) * WINDOW for r in good]
    total = [sum(int(r[i]) for i in rb) for r in good]
    for o in range(4):
        v = [int(r[col[o]]) for r in good]
        print(f"occ {o}: mean {st.mean(v):>9,.0f} min {min(v):>9,} max {max(v):>9,}  r {pearson(hp, v):+.2f} rank {pearson(ranks(hp), ranks(v)):+.2f} slope {slope(hp, v):+.2f}")
    print(f"frame total: mean {st.mean(total):>9,.0f}  r {pearson(hp, total):+.2f} rank {pearson(ranks(hp), ranks(total)):+.2f} slope {slope(hp, total):+.2f}")
    caps = {}
    for r in good:
        caps.setdefault(r[2].split(".")[0], []).append(r)
    print("capture frames holes occ0 occ1 occ2 occ3 sum total sides")
    ch, cs, ct = [], [], []
    for c in sorted(caps):
        g = caps[c]
        h = st.mean(float(r[4]) * WINDOW for r in g)
        m = [st.mean(int(r[col[o]]) for r in g) for o in range(4)]
        t = st.mean(sum(int(r[i]) for i in rb) for r in g)
        ch.append(h), cs.append(sum(m)), ct.append(t)
        print(f"{c} {len(g)} {h:>8,.0f} " + " ".join(f"{x:>8,.0f}" for x in m) + f" {sum(m):>10,.0f} {t:>10,.0f} {''.join(r[5] for r in g)}")
    print(f"over {len(ch)} captures: the four draws against hole pixels r {pearson(ch, cs):+.2f} slope {slope(ch, cs):+.2f}; frame total r {pearson(ch, ct):+.2f} slope {slope(ch, ct):+.2f}")
    return good, col, rb


def levels(good, col, o, step=10000):
    bins = {}
    for r in good:
        b = int(r[col[o]]) // step * step
        bins[b] = bins.get(b, 0) + 1
    print(f"occ {o} per frame, {step:,} wide bins: " + " ".join(f"{k // 1000}k:{v}" for k, v in sorted(bins.items())))


def labels(good, col):
    for s in "AB?":
        g = [r for r in good if r[5] == s]
        if g:
            print(f"side {s}: {len(g)} frames, holes {st.mean(float(r[4]) * WINDOW for r in g):,.0f}, " + " ".join(f"occ {o} {st.mean(int(r[col[o]]) for r in g):,.0f}" for o in range(4)))


def within(tag):
    """Per-frame test the slow change can't pass by itself: each capture's own mean taken away, holes against a draw at a lag of lake jobs."""
    with gzip.open(os.path.join(RAW, tag + ".jobs.tsv.gz"), "rt") as f:
        rows = [l.rstrip("\n").split("\t") for l in f]
    head, body = rows[0], sorted(rows[1:], key=lambda r: float(r[1]))
    cols = {}
    for i, h in enumerate(head):
        if ":" in h and h.split(":")[1].startswith(PS):
            cols.setdefault(int(h.split(".")[-1]), []).append(i)
    at = {r[0]: i for i, r in enumerate(body)}
    caps = {}
    for r in body:
        if r[2] != "-" and r[3] == "2560":
            caps.setdefault(r[2].split(".")[0], []).append(r)
    for o in range(4):
        line = f"{tag} occ {o}:"
        for lag in (-2, -1, 0, 1, 2):
            xs, ys = [], []
            for rs in caps.values():
                pairs = []
                for r in rs:
                    i = at[r[0]] + lag
                    if 0 <= i < len(body) and abs(float(body[i][1]) - float(r[1]) - lag * 33) < 12:
                        pairs.append((float(r[4]), sum(int(body[i][c]) for c in cols[o])))
                if len(pairs) >= 3:
                    mh, mv = st.mean(p[0] for p in pairs), st.mean(p[1] for p in pairs)
                    xs += [p[0] - mh for p in pairs]
                    ys += [p[1] - mv for p in pairs]
            line += f"  {lag:+d} r {pearson(xs, ys):+.2f} n {len(xs)}"
        print(line)


def metric(tag, pad_shot=8):
    """Shots against the captures: shots are named by clock time, and the pad line ties shot 8 to the wall clock."""
    pad = int(text(tag + ".pad.txt").split()[1])
    shots = re.findall(r"^(\d\d)(\d\d)(\d\d)-ts(\d+)\.png: patch\s+([0-9.]+)", text(tag + ".patch.txt"), re.M)
    sec = lambda s: int(s[0]) * 3600 + int(s[1]) * 60 + int(s[2])
    base = next(sec(s) for s in shots if int(s[3]) == pad_shot)
    wall = {f"{m[0]}.{m[1]}": float(m[2]) for m in re.findall(r"^(c\d+) (f\d+) sF wall ([0-9.]+)", text(tag + ".snaps.txt"), re.M)}
    caps = {}
    for name, h in re.findall(r"^\s+(c\d+\.f\d+) w \d+ holes ([0-9.]+)", text(tag + ".tz.txt"), re.M):
        if name in wall:
            caps.setdefault(name.split(".")[0], []).append((wall[name], float(h)))
    centre = [(st.mean(x[0] for x in g), st.mean(x[1] for x in g)) for g in caps.values()]
    xs, ys = [], []
    print(f"{tag}: shot patch nearest captures' holes")
    for s in shots:
        t = pad + sec(s) - base
        near = [c for c in centre if abs(c[0] - t) <= 2.5]
        if near:
            h = st.mean(c[1] for c in near)
            xs.append(h), ys.append(float(s[4]))
            print(f"ts{s[3]} {s[4]:>5} {h:.3f}")
    print(f"{len(xs)} shots: patch against hole share r {pearson(xs, ys):+.2f} rank {pearson(ranks(xs), ranks(ys)):+.2f}")


def main():
    good, col, _ = draws("N2")
    for o in (0, 2):
        levels(good, col, o)
    labels(good, col)
    within("N2")
    metric("N2")
    good, col, _ = draws("N1")
    levels(good, col, 0, 50000)
    labels(good, col)
    within("N1")


if __name__ == "__main__":
    main()
