#!/usr/bin/env python3
"""BC5 exp 0412 (README section 26): the per-buffer time line of a run with BC5_GUARD_BUF_STAT (build g412n), play phase.
Lines (buf0412.inc): B handed, S submission n (chain opened, flushed), D fence seen, W label wait, f flip called, F drain ended.
Note on S: its third time is not used (it is the previous submission's); "flushed" is when the host took the chain to
submit it, and the kernel has it some 0.3-1 ms later (section 21).
Printed, for the play phase [<load at> + 28 s, end):
  1. the host's queue: chain opened -> flushed, by thread, kind and reason of the flush; buffer handed -> flushed;
  2. flushed -> fence seen (the kernel's queue plus the GPU's run);
  3. the frame's time line for frames of 33-50 ms: when the title hands buffers, when the host flushes, when fences
     come back, when the flip is called and returns; how long nothing is in flight and where in the frame;
  4. the label waits: time, labels, and whether the submission whose fence ended the wait had been flushed before
     the wait began (then the wait is GPU time) or after it (then it sat in the host's queue).
usage: buf0412.py <buf file> [<load at s> default 104]"""
import bisect
import collections
import statistics
import sys

SLOT = ("Render Thread", "game-main", "bc5-ring", "bc5-cq0", "bc5-chainwd", "others")
WHY = {0: "end of the call", 1: "a wait", 2: "ring or class change", 3: "cond_exec", 4: "size", 5: "drain or flip", 6: "6", 7: "7", 8: "8", 9: "foreign (9)", 10: "10", 11: "watchdog (11)", -1: "no chain"}


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0.0


def main():
    load_at = float(sys.argv[2]) if len(sys.argv) > 2 else 104.0
    P0 = load_at + 28
    B, S, D, W, fl, Fl = [], {}, {}, [], [], []
    for ln in open(sys.argv[1], errors="replace"):
        p = ln.split()
        if not p:
            continue
        try:
            if p[0] == "B" and len(p) == 5:
                B.append((float(p[1]), int(p[2]), p[3], int(p[4])))
            elif p[0] == "S" and len(p) == 10:
                S[int(p[1])] = (float(p[2]), float(p[3]), int(p[5]), p[6], int(p[7]), int(p[8]), int(p[9]))
            elif p[0] == "D" and len(p) == 6:
                D[int(p[1])] = float(p[2])
            elif p[0] == "W" and len(p) == 5:
                W.append((float(p[1]), float(p[2]), p[3], int(p[4])))
            elif p[0] == "f":
                fl.append(float(p[1]))
            elif p[0] == "F":
                Fl.append(float(p[1]))
        except ValueError:
            continue
    t_end = Fl[-1]
    Sp = {n: s for n, s in S.items() if P0 <= s[1] <= t_end}
    print(f"play phase {P0:.0f}-{t_end:.0f} s: {len([b for b in B if P0 <= b[0] <= t_end])} buffers handed, {len(Sp)} submissions, "
          f"{len([f for f in Fl if P0 <= f <= t_end])} flips, {len([w for w in W if P0 <= w[0] <= t_end])} label waits")
    # 1. the host's queue
    print("\n== 1. the host's queue: chain opened -> flushed (ms), by thread, kind and reason of the flush")
    grp = collections.defaultdict(list)
    for n, (to, tf, slot, kind, dw, segs, why) in Sp.items():
        grp[(SLOT[slot], kind, WHY.get(why, str(why)))].append(((tf - to) * 1000, segs, dw))
    for k, v in sorted(grp.items(), key=lambda kv: -len(kv[1])):
        if len(v) < 20:
            continue
        ages = [a for a, _, _ in v]
        print(f"   {k[0]:13s} {k[1]:4s} flushed by {k[2]:22s}: {len(v):6d} submissions ({len(v) / (t_end - P0):6.1f}/s), {statistics.mean(s for _, s, _ in v):4.1f} segments, "
              f"{statistics.mean(d for _, _, d in v):7.0f} dwords; open -> flush median {q(ages, 0.5):6.2f}, p90 {q(ages, 0.9):6.2f}, max {max(ages):7.1f} ms")
    st = sorted((s[1], n) for n, s in S.items())
    by_slot = collections.defaultdict(list)
    for n, s in S.items():
        by_slot[s[2]].append(s[1])
    for v in by_slot.values():
        v.sort()
    hd = collections.defaultdict(list)
    for t, slot, kind, dw in B:
        if not (P0 <= t <= t_end):
            continue
        v = by_slot.get(slot, [])
        k = bisect.bisect_left(v, t)
        if k < len(v):
            hd[(SLOT[slot], kind)].append((v[k] - t) * 1000)
    print("   buffer handed -> the next flush of the same thread (ms):")
    for k, v in sorted(hd.items(), key=lambda kv: -len(kv[1])):
        if len(v) >= 50:
            print(f"      {k[0]:13s} {k[1]:4s}: {len(v):6d} buffers, median {q(v, 0.5):6.2f}, p90 {q(v, 0.9):6.2f}, p99 {q(v, 0.99):7.1f}")
    # 2. flushed -> fence seen
    lat = collections.defaultdict(list)
    for n, s in Sp.items():
        if n in D:
            lat[(SLOT[s[2]], s[3])].append((D[n] - s[1]) * 1000)
    print("\n== 2. flushed -> fence seen by the completion thread (ms; the host's submit work, the kernel's queue and the GPU's run)")
    for k, v in sorted(lat.items(), key=lambda kv: -len(kv[1])):
        if len(v) >= 20:
            print(f"   {k[0]:13s} {k[1]:4s}: {len(v):6d}, median {q(v, 0.5):6.2f}, p90 {q(v, 0.9):6.2f}, max {max(v):7.1f}")
    # 3. the frame's time line
    iv = sorted((s[1], D[n]) for n, s in S.items() if n in D)
    Fp = [f for f in Fl if P0 <= f <= t_end]
    rows = []
    for a, b in zip(Fp, Fp[1:]):
        ms = (b - a) * 1000
        if not (33 < ms <= 50):
            continue
        bs = [x[0] for x in B[bisect.bisect_left(B, (a,)):bisect.bisect_left(B, (b,))]]
        ss = [t for t, n in st[bisect.bisect_left(st, (a,)):bisect.bisect_left(st, (b,))]]
        ds = sorted(t for t in (D.get(n) for t0, n in st[bisect.bisect_left(st, (a - 0.2,)):bisect.bisect_left(st, (b,))]) if t is not None and a <= t <= b)
        k = bisect.bisect_left(fl, a)
        fc = fl[k] if k < len(fl) and fl[k] <= b else None
        if not bs or not ss or not ds or fc is None:
            continue
        # time with nothing in flight inside [a, b]
        cov, cur = 0.0, a
        idle_parts = [0.0, 0.0, 0.0]  # before the first flush, between, after the last fence
        for x, y in iv[bisect.bisect_left(iv, (a - 0.5,)):]:
            if x >= b:
                break
            x, y = max(x, a), min(y, b)
            if y <= cur:
                continue
            if x > cur:
                gap = x - cur
                idle_parts[0 if cur == a else 1] += gap
                cur = x
            cov += y - cur
            cur = y
        if cur < b:
            idle_parts[2] += b - cur
        rows.append((ms, (bs[0] - a) * 1000, (bs[-1] - a) * 1000, (ss[0] - a) * 1000, (ss[-1] - a) * 1000, (ds[-1] - a) * 1000, (fc - a) * 1000, len(bs), len(ss),
                     idle_parts[0] * 1000, idle_parts[1] * 1000, idle_parts[2] * 1000))
    if rows:
        m = lambda i: statistics.median(r[i] for r in rows)
        print(f"\n== 3. the time line of a frame of 33-50 ms ({len(rows)} frames; medians, ms from the end of the previous flip's drain)")
        print(f"   frame {m(0):.1f} ms; {m(7):.0f} buffers handed, {m(8):.0f} submissions")
        print(f"   first buffer handed at {m(1):.1f}, last at {m(2):.1f}; first flush at {m(3):.1f}, last flush at {m(4):.1f}; last fence at {m(5):.1f}; flip called at {m(6):.1f}; drain ended at {m(0):.1f}")
        print(f"   nothing in flight (flushed and not yet fenced): {m(9):.1f} ms before the frame's first flush, {m(10):.1f} ms between submissions, {m(11):.1f} ms after the last fence")
        deciles = [0] * 10
        cnt = 0
        for a, b in zip(Fp, Fp[1:]):
            ms = (b - a) * 1000
            if not (33 < ms <= 50):
                continue
            for t, n in st[bisect.bisect_left(st, (a,)):bisect.bisect_left(st, (b,))]:
                deciles[min(9, int(10 * (t - a) / (b - a)))] += S[n][4]
                cnt += S[n][4]
        print("   dwords flushed by tenth of the frame, %: " + " ".join(f"{100 * d / cnt:.0f}" for d in deciles))
    # 4. the label waits
    Wp = [w for w in W if P0 <= w[0] <= t_end and w[1] > w[0]]
    if Wp:
        tot = sum(w[1] - w[0] for w in Wp)
        dn = sorted((t, n) for n, t in D.items())
        dt = [x[0] for x in dn]
        before = after = none = 0.0
        qd = []
        labels = collections.Counter()
        for a, b, lab, slot in Wp:
            labels[lab] += b - a
            k = bisect.bisect_right(dt, b + 0.0005) - 1
            if k < 0 or dt[k] < a - 0.0005:
                none += b - a
                continue
            n = dn[k][1]
            s = S.get(n)
            if s is None:
                none += b - a
                continue
            if s[1] <= a:
                before += b - a
            else:
                after += b - a
                qd.append((s[1] - a) * 1000)
        durs = [(w[1] - w[0]) * 1000 for w in Wp]
        print(f"\n== 4. label waits in the play phase: {len(Wp)} waits, {tot:.1f} s ({100 * tot / (t_end - P0):.1f} % of the phase), median {q(durs, 0.5):.2f} ms, p90 {q(durs, 0.9):.2f} ms; "
              f"by thread: " + ", ".join(f"{SLOT[s]} {sum(w[1] - w[0] for w in Wp if w[3] == s):.1f} s" for s in sorted({w[3] for w in Wp})))
        print(f"   the submission whose fence came at the wait's end had been flushed BEFORE the wait began: {100 * before / tot:.0f} % of the wait time (the GPU's time);")
        print(f"   flushed AFTER the wait began: {100 * after / tot:.0f} % (it was still in the host's hands; flushed a median {q(qd, 0.5):.2f} ms, p90 {q(qd, 0.9):.2f} ms into the wait); no fence at the wait's end: {100 * none / tot:.0f} %")
        print("   labels by wait time: " + ", ".join(f"{lab} {100 * v / tot:.0f} %" for lab, v in labels.most_common(6)) + f" ({len(labels)} labels)")


if __name__ == "__main__":
    main()
