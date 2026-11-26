#!/usr/bin/env python3
"""BC5 exp 0388, memory: the leak rule applied to one leak0389m.sh record.

A quantity is SUSTAINED when, after the load (t >= 600 s), it rises in each of three equal thirds of the rest of the play,
by more than 32 MiB in each, and the last third's slope is at least half of the first third's, so it does not flatten. That
is a leak suspect, not a proof: data kept on purpose (a cache, the title's own buffers) meets it too. It is STEPPED when it
grows after the load but in steps that stop: at least one third with a rise under 32 MiB, or a last third under half the
first's slope. That fits the title streaming and does not prove it. It is FLAT when the whole rise after the load is under
64 MiB. Falls count as flat or
noted. SUSTAINED needs at least 30 minutes after the load; a shorter play gives OPEN. A sum whose part was not read
(-1) is unknown, not a number, and its samples are left out.

The rule reads the emulator's own memory (e_anon, e_shmem, e_rss + e_swap), the mount (m_pss + m_swap), GTT, shmem,
slab (sunreclaim) and zram's stored data. A leak in the emulator's anonymous memory with the title's pinned memory flat
points at the host; a leak in shmem points at memfds; in sunreclaim at the kernel. Page cache is not tested: it fills
by design, and avail and PSI show its cost instead.
usage: leak0389.py <record>"""
import re
import sys

LOAD, STEP, FLATTOTAL, MINPLAY = 600, 32, 64, 1800
KEYS = ["e_anon", "e_shmem", "e_rss+e_swap", "m_pss+m_swap", "gtt", "shmem", "sunreclaim", "zram_orig", "avail"]


def total(*parts):
    """A sum of read values, or -1 (unknown) when any part was not read."""
    return -1 if any(p < 0 for p in parts) else sum(parts)


def rows(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if not line.startswith("t="):
            continue
        d = dict(re.findall(r"(\w+)=(-?\d+)\b", line))
        r = {k: int(v) for k, v in d.items()}
        r["e_rss+e_swap"] = total(r.get("e_rss", -1), r.get("e_swap", -1))
        r["m_pss+m_swap"] = total(r["m_pss"] if r.get("m_pss", -1) >= 0 else r.get("m_rss", -1), r.get("m_swap", -1))
        out.append(r)
    return out


def verdict(series):
    after = [(t, v) for t, v in series if t >= LOAD and v >= 0]
    if len(after) < 6:
        return "OPEN", "too few samples after the load"
    t0, t1 = after[0][0], after[-1][0]
    span = t1 - t0
    if after[-1][1] - after[0][1] < FLATTOTAL:
        return "FLAT", f"{after[0][1]} -> {after[-1][1]} MiB"
    cuts = [t0 + span * k / 3 for k in range(4)]
    parts = [[v for t, v in after if cuts[k] <= t <= cuts[k + 1]] for k in range(3)]
    rise = [p[-1] - p[0] if len(p) > 1 else 0 for p in parts]
    text = f"{after[0][1]} -> {after[-1][1]} MiB over {span // 60} min after the load, thirds +{rise[0]} +{rise[1]} +{rise[2]}"
    if span < MINPLAY:
        return "OPEN", text + f", under {MINPLAY // 60} min after the load"
    if all(r > STEP for r in rise) and rise[2] >= rise[0] / 2:
        return "SUSTAINED", text + " (leak suspect, not proof)"
    return "STEPPED", text


def main():
    r = rows(sys.argv[1])
    if not r:
        print("no samples")
        return 1
    print(f"{len(r)} samples, t {r[0]['t']} to {r[-1]['t']} s")
    for k in KEYS:
        v, why = verdict([(x["t"], x.get(k, -1)) for x in r])
        if k == "avail":
            print(f"{k:14s} (not judged) {why}")
        else:
            print(f"{k:14s} {v:8s} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
