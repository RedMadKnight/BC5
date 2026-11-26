#!/usr/bin/env python3
# BC5 exp 0439 (tag fr439): one run's figures for the 19:01-freeze separation, from its memory sampler (ms439 columns)
# and its journal: GTT used and unevictable at 30 / 60 / 85 / 108 s after the sampler's first line, the lowest
# MemAvailable, the largest memory PSI full and IO PSI full (avg10), the frame time median and p90 from the journal's
# "frame profile" lines between 40 and 150 s of emulator time, and the journal lines with "TIMED OUT".
#   fr439.py <memsample.txt> <direct.log>
import sys


def hms(s):
    h, m, x = s.split(':')
    return int(h) * 3600 + int(m) * 60 + float(x)


ms, dl = sys.argv[1], sys.argv[2]
rows = []
hdr = None
for line in open(ms, errors='replace'):
    if line.startswith('#'):
        hdr = line.split(':', 1)[1].split()[1:] if ':' in line else None
        continue
    c = line.split()
    if len(c) < 20:
        continue
    try:
        rows.append((hms(c[0]), [float(x) for x in c[1:]]))
    except ValueError:
        pass
cols = 'mem_avail_kB swap_free_kB dirty_kB gtt_used_MiB vram_used_MiB emu_pid rss_anon_kB rss_shmem_kB cpu_maps unevictable_kB shmem_kB sunreclaim_kB pagetables_kB mlocked_kB vmpte_kB psi_mem_some10 psi_mem_full10 psi_io_full10 allocstall pgscan_direct'.split()
ix = {k: i for i, k in enumerate(cols)}
t0 = rows[0][0]


def at(t):
    best = min(rows, key=lambda r: abs(r[0] - t0 - t))
    return best[1] if abs(best[0] - t0 - t) < 3 else None


out = []
for t in (30, 60, 85, 108):
    r = at(t)
    out.append('%ds GTT %s unev %s' % (t, '%.0f' % r[ix['gtt_used_MiB']] if r else '-', '%.0f' % (r[ix['unevictable_kB']] / 1024) if r else '-'))
mn = min(r[1][ix['mem_avail_kB']] for r in rows) / 1024
pm = max(r[1][ix['psi_mem_full10']] for r in rows)
pio = max(r[1][ix['psi_io_full10']] for r in rows)
ft = []
tos = 0
for line in open(dl, errors='replace'):
    if line.startswith('frame profile: t '):
        try:
            t = float(line.split()[3])
            v = float(line.split(',')[1].split()[0])
        except (ValueError, IndexError):
            continue
        if 40 <= t <= 150:
            ft.append(v)
    elif 'TIMED OUT' in line:
        tos += 1
ft.sort()
med = ft[len(ft) // 2] if ft else 0
p90 = ft[int(len(ft) * 0.9)] if ft else 0
print('%s | lowest MemAvailable %.0f MiB | PSI mem full max %.2f, IO full max %.2f | frame median %.1f p90 %.1f ms (%d frames 40-150 s) | TIMED OUT lines %d'
      % ('; '.join(out), mn, pm, pio, med, p90, len(ft), tos))
