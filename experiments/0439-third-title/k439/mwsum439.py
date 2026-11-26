#!/usr/bin/env python3
# BC5 exp 0439 (tag mw439): summary of a memory-wall run. Reads the 1-s sampler file (memsample439.sh) and the
# emulator's log (BC5_GUARD_LEDGER=1 guard lines, "[bc5-direct] mappings:" lines, BC5_DIRECT_BREAKDOWN growth rows).
#   mwsum439.py <sampler.txt> <play-last.log> [step_s=120]
import re, sys

samp, log = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 120


def secs(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


rows = []
for ln in open(samp, errors='replace'):
    if ln.startswith('#'):
        continue
    f = ln.split()
    if len(f) < 10 or f[6] == '-':
        continue
    try:
        rows.append((secs(f[0]), int(f[1]), int(f[2]), int(f[3]), f[4], f[5], f[7], f[8], f[9]))
    except ValueError:
        pass
print(f"sampler: {len(rows)} seconds with the emulator")
if rows:
    t0 = rows[0][0]
    print(" t(s)  avail_MiB swapfree_MiB dirty_MiB gtt_MiB vram_MiB rssanon_MiB rssshmem_MiB cpu_maps")
    nxt = 0
    for r in rows:
        el = r[0] - t0
        if el >= nxt or r is rows[-1]:
            ra = int(r[6]) // 1024 if r[6].isdigit() else r[6]
            rs = int(r[7]) // 1024 if r[7].isdigit() else r[7]
            print(f"{el:5.0f} {r[1] // 1024:9d} {r[2] // 1024:12d} {r[3] // 1024:9d} {r[4]:>7} {r[5]:>8} {ra!s:>11} {rs!s:>12} {r[8]:>8}")
            nxt += step
    mn = min(rows, key=lambda r: r[1])
    print(f"min MemAvailable {mn[1] // 1024} MiB at {mn[0] - t0:.0f} s; min SwapFree {min(r[2] for r in rows) // 1024} MiB")

G = re.compile(r'guard: t (\d+) s: pinned direct ([\d.]+) MiB, private ([\d.]+); under a view ([\d.]+), orphans ([\d.]+); views (\d+) over ([\d.]+) MiB; gtt ([\d.]+); rss (-?\d+) shmem (-?\d+) swap (-?\d+) MiB.*?avail (-?\d+).*?guard locked ([\d.]+) MiB, guest views (\d+)')
M = re.compile(r'\[bc5-direct\] mappings: \+(\d+) -(\d+), (\d+) total, ([\d.]+) MiB \(rw anon VMAs: (\d+), ([\d.]+) MiB, ([\d.]+) MiB resident\)')
B = re.compile(r'by name \((growth|ENOMEM)\): (\d+) BOs, ([\d.]+) MiB imported; BO list of the submit (\d+); GTT ([\d.]+) of')
guards, maps, bds, heaps, other = [], [], [], [], {}
KEYS = ['slot', 'regrow', 'K1r', 'cover', 'merge', 'lazy release', 'zero scan', 'ENOMEM', 'oom', 'vd439', 'nm439']
for ln in open(log, errors='replace'):
    g = G.search(ln)
    if g:
        guards.append(g.groups())
        continue
    m = M.search(ln)
    if m:
        maps.append(m.groups())
        continue
    b = B.search(ln)
    if b:
        bds.append(b.groups())
        continue
    if 'guard heaps' in ln:
        heaps.append(ln.strip())
    for k in KEYS:
        if k in ln:
            other[k] = other.get(k, 0) + 1
print(f"\nguard ledger: {len(guards)} lines")
print("  t(s) pinned_direct private under_view orphans views reserved gtt rss shmem swap avail locked guest_views")
for i, g in enumerate(guards):
    if i % max(1, step // 10) == 0 or i == len(guards) - 1:
        print('  ' + ' '.join(g))
print(f"\nmappings lines: {len(maps)}; first/last:")
for m in (maps[:1] + maps[-1:]):
    print('  +%s -%s total %s mapped %s MiB; anon VMAs %s %s MiB, %s resident' % m)
print(f"\nBO breakdowns: {len(bds)}")
for b in bds:
    print('  %s: %s BOs, %s MiB imported, list %s, GTT %s MiB' % b)
if heaps:
    print("\nfirst and last guard heaps:\n  " + heaps[0][:700] + "\n  " + heaps[-1][:700])
print("\nkeyword counts in the log:", other)
