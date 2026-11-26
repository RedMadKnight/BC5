#!/usr/bin/env python3
"""BC5 exp 0412: one line per night arm from run0412n.sh's files (fetched to a directory on the laptop).
For each tag: how it ended; the ledger's pinned total (direct + private), orphans, cap put-off and cgroup MiB at the
ledger's t nearest 130 s and 240 s; from the sampler the lowest MemAvailable, the highest PSI full, the box's major faults
per second and the emulator's anon + swap; from the journal's frame profile lines the flips, the median and the 95th
percentile of the frame time and the share of frames over 100 ms, in the window from the load + 45 s to the end.
usage: sum0412n.py <dir> <tag> [<tag> ...]"""
import os
import re
import sys


def rd(d, tag, name):
    p = os.path.join(d, f"{tag}-{name}")
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def ledger(text):
    rows = []
    for ln in text.splitlines():
        m = re.match(r"guard: t (\d+) s: pinned direct ([\d.]+) MiB, private ([\d.]+); under a view ([\d.]+), orphans ([\d.]+)", ln)
        if not m:
            continue
        t, pd, pp, _, orph = (float(x) for x in m.groups())
        cg = re.search(r"cgroup (-?\d+) MiB", ln)
        off = re.search(r"cap put off ([\d.]+) MiB \(max ([\d.]+)", ln)
        anon = re.search(r"rss anon (-?\d+)", ln)
        rows.append(dict(t=t, pin=pd + pp, orph=orph, cg=int(cg.group(1)) if cg else -1, off=float(off.group(1)) if off else 0.0,
                         offmax=float(off.group(2)) if off else 0.0, anon=int(anon.group(1)) if anon else -1))
    return rows


def near(rows, t):
    if not rows:
        return None
    r = min(rows, key=lambda x: abs(x["t"] - t))
    return r if abs(r["t"] - t) <= 12 else None


def pct(v, p):
    if not v:
        return float("nan")
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def main():
    d, tags = sys.argv[1], sys.argv[2:]
    for tag in tags:
        end = rd(d, tag, "end.txt").strip()
        start = rd(d, tag, "start.txt")
        m = re.search(r"load (?:seen )?at (\d+) s", start)
        load = int(m.group(1)) if m else None
        g = re.search(r"G = (\d+) s( BY TIME)?", start)
        L = ledger(rd(d, tag, "guard.txt"))
        lz = [ln for ln in rd(d, tag, "guard.txt").splitlines() if ln.startswith("lazy release") and "cut " in ln]
        samp = []
        for ln in rd(d, tag, "sampler.txt").splitlines():
            if ln.startswith("#"):
                continue
            f = [x.strip() for x in ln.split(" | ")]
            if len(f) < 10:
                continue
            a = f[1].split()
            e = f[6].split()
            try:
                samp.append(dict(t=int(f[0]), avail=int(a[0]), swap=int(a[1]), maj=float(a[4]), full=float(f[2].split()[0].split("/")[1]),
                                 anon=int(e[0]), eswap=int(e[2]), cg=int(f[8].split()[0]) if f[8].split()[0] != "-" else -1))
            except (ValueError, IndexError):
                pass
        fr = []
        for ln in rd(d, tag, "frames.txt").splitlines():
            p = ln.split()
            if len(p) == 5:
                fr.append(tuple(float(x) for x in p))
        t0 = (load + 45) if load is not None else 1e9
        w = [x for x in fr if x[0] >= t0]
        dur = (w[-1][0] - w[0][0]) if len(w) > 1 else 0.0
        ms = [x[1] for x in w]
        ws = [x for x in samp if x["t"] >= t0]
        print(f"== {tag}: {end}")
        print(f"   load at {load} s, G {g.group(1) + (' by time' if g.group(2) else '') if g else 'none'}; ledger lines {len(L)}; last ledger t {L[-1]['t']:.0f} s" if L else f"   load at {load} s; no ledger lines")
        for t in (60, 130, 240):
            r = near(L, t)
            if r:
                print(f"   t {r['t']:.0f} s: pinned {r['pin']:.0f} MiB, orphans {r['orph']:.0f}, cap put off {r['off']:.0f} (max {r['offmax']:.0f}), cgroup {r['cg']}, emu anon {r['anon']}")
        if L:
            print(f"   pinned max {max(x['pin'] for x in L):.0f} MiB; orphans max {max(x['orph'] for x in L):.0f}; cgroup max {max(x['cg'] for x in L)}")
        if samp:
            print(f"   sampler: avail min {min(x['avail'] for x in samp)} MiB, PSI full max {max(x['full'] for x in samp):.1f} %, swap used max {max(x['swap'] for x in samp)} MiB; "
                  f"after load+45: majflt/s mean {sum(x['maj'] for x in ws) / max(1, len(ws)):.0f}, PSI full mean {sum(x['full'] for x in ws) / max(1, len(ws)):.1f} %")
        if w:
            print(f"   frames after load+45 ({dur:.0f} s): {len(w)} flips = {len(w) / dur if dur else 0:.1f}/s, median {pct(ms, 0.5):.0f} ms, p95 {pct(ms, 0.95):.0f} ms, "
                  f"over 100 ms {100.0 * sum(1 for x in ms if x > 100) / len(ms):.1f} %, longest {max(ms):.0f} ms; outside-host median {pct([x[3] for x in w], 0.5):.0f} ms, GPU median {pct([x[4] for x in w], 0.5):.0f} ms")
        else:
            print("   frames after load+45: none")
        if lz:
            print(f"   lazy release: {len(lz)} cut lines; last: {lz[-1][:230]}")


if __name__ == "__main__":
    main()
