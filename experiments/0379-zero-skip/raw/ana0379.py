# BC5 experiment 0379: one table row per arm from the committed raw files, over the same window of each run.
# <tag>-mem.txt (sample0379.sh, every 10 s; t from its first sample) and <tag>-flips-per-10s.txt (journal t).
# Medians of GTT used, MemAvailable, swap used, Shmem, Cached; rates over the window of bc5-mount reads (MiB/min), PSI
# memory and io "full" (% of wall time), refaults and major faults (per min); flips/s over the window.
# usage: python -I ana0379.py <raw dir> <from s> <to s> <tag> [<tag> ...]
import os, statistics, sys
raw, lo, hi, tags = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4:]
cols = "uptime avail swapused shmem cached gtt_used psi_mem_full_us psi_io_full_us mount_read_mib mount_rss emu_rss pswpin pswpout pgmajfault refault_file".split()
print("| arm | GTT used MiB | MemAvailable MiB (min) | swap used MiB | Shmem MiB | Cached MiB | mount reads MiB/min | PSI mem full % | PSI io full % | refaults /min | major faults /min | flips/s |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for tag in tags:
    rows = []
    for line in open(os.path.join(raw, f"{tag}-mem.txt")):
        if line.startswith("#"): continue
        f = line.split()
        if len(f) != len(cols): continue
        rows.append(dict(zip(cols, map(float, f))))
    t0 = rows[0]["uptime"]
    w = [r for r in rows if lo <= r["uptime"] - t0 <= hi]
    a, b = w[0], w[-1]
    mins = (b["uptime"] - a["uptime"]) / 60.0
    med = lambda k: statistics.median(r[k] for r in w)
    rate = lambda k: (b[k] - a[k]) / mins
    pct = lambda k: 100.0 * (b[k] - a[k]) / 1e6 / (b["uptime"] - a["uptime"])
    fl = [tuple(map(int, l.split())) for l in open(os.path.join(raw, f"{tag}-flips-per-10s.txt")) if l.strip()]
    fw = [n for s, n in fl if lo <= s and s + 10 <= hi]
    fps = sum(fw) / (10.0 * len(fw)) if fw else 0.0
    mr = rate("mount_read_mib") if a["mount_read_mib"] >= 0 and b["mount_read_mib"] >= 0 else float("nan")
    print(f"| {tag} | {med('gtt_used'):.0f} | {med('avail'):.0f} ({min(r['avail'] for r in w):.0f}) | {med('swapused'):.0f} | {med('shmem'):.0f} | {med('cached'):.0f} | {mr:.0f} | {pct('psi_mem_full_us'):.2f} | {pct('psi_io_full_us'):.2f} | {rate('refault_file'):.0f} | {rate('pgmajfault'):.0f} | {fps:.1f} |")
print(f"\nwindow {lo:.0f}-{hi:.0f} s of each run ({len(w)} samples in the last arm)")
