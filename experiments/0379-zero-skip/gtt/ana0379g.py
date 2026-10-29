# BC5 experiment 0379, GTT growth (G1/G2): per minute of a gtt/sample0379m.sh record, GTT used, each DRM client's
# total/resident/shared GTT, MemAvailable, swap, PSI mem/io full over the minute (%), mount reads over the minute (MiB)
# and the emulator's RSS; then GTT at 180 s and at the end, and the change between them.
# usage: python ana0379g.py <G?-mem.txt> [...]
import sys
for path in sys.argv[1:]:
    rows = []
    for line in open(path):
        if line.startswith("#"): continue
        f = line.split()
        if len(f) < 15: continue
        cl = {x.split("=")[0]: x.split("=")[1] for x in f[15:] if "=" in x}
        rows.append((float(f[0]), [int(x) for x in f[1:15]], cl))
    if not rows: print(path, "no samples"); continue
    t0 = rows[0][0]
    print(f"== {path}: {len(rows)} samples over {rows[-1][0] - t0:.0f} s")
    print("min  gtt   memavail swap  psi_mem% psi_io% mount_MiB emu_rss | clients total/resident/shared")
    prev = rows[0]
    for r in rows:
        s = r[0] - t0
        if int(s) // 60 == int(prev[0] - t0) // 60 and r is not rows[-1]: continue
        dt = max(r[0] - prev[0], 1e-9)
        v, p = r[1], prev[1]
        print(f"{s / 60:4.1f} {v[4]:6d} {v[0]:6d} {v[1]:6d} {100 * (v[5] - p[5]) / 1e6 / dt:6.2f} {100 * (v[6] - p[6]) / 1e6 / dt:6.2f}"
              f" {v[7] - p[7]:7d} {v[9]:6d} | {' '.join(f'{k}={x}' for k, x in sorted(r[2].items()))}")
        prev = r
    a = min(rows, key=lambda r: abs(r[0] - t0 - 180))
    print(f"GTT at {a[0] - t0:.0f} s {a[1][4]} MiB, at the end {rows[-1][1][4]} MiB, change {rows[-1][1][4] - a[1][4]:+d} MiB;"
          f" clients at 180 s {a[2]}, at the end {rows[-1][2]}")
