#!/usr/bin/env python3
# BC5 exp 0381: flips per minute against the mount's reads for one play, from the play log and the minute sampler. Paths at the top.
import re, statistics as st, math
T = 'C:/Users/kjani/AppData/Local/Temp/claude/C--Users-kjani-Downloads-bc5/cffe3f93-6cbd-4474-8dee-365d1506f277/scratchpad/'
log = T + 'play-20261031-200140.log'
mem = T + 'mem-20261031-200140.txt'
t0 = 20 * 3600 + 1 * 60 + 41
rows = []
for l in open(mem, errors='replace'):
    m = re.match(r'(\d+):(\d+):(\d+) emu=(\S+) memavail=(\d+)M swapused=(\d+)M gtt=(\d+)M emu_rss=(\S+)M mount_rss=(\d+)M mount_read_1min=(\S+)M psi_mem_full60=(\S+) psi_io_full60=(\S+)', l)
    if m and m[10] != '-':
        rows.append(dict(s=int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]), avail=int(m[5]), swap=int(m[6]), gtt=int(m[7]), rss=m[8], mrss=int(m[9]), rd=int(m[10]), pm=float(m[11]), pio=float(m[12])))
fps = []
for l in open(log, errors='replace'):
    m = re.match(r'fps counter: t ([\d.]+) s: (\d+) flips in ([\d.]+) s, longest gap ([\d.]+) ms, gaps over 40 ms (\d+), over 70 ms (\d+)', l)
    if m:
        fps.append((float(m[1]), int(m[2]), float(m[3]), float(m[4])))
print('fps lines', len(fps), 'span', fps[0][0], fps[-1][0])
out = []
for i in range(1, len(rows)):
    a, b = rows[i - 1]['s'] - t0, rows[i]['s'] - t0
    w = [f for f in fps if a < f[0] <= b]
    fl = sum(f[1] for f in w)
    dur = sum(f[2] for f in w) or 1
    gap = max([f[3] for f in w] or [0])
    secs = [f[1] / f[2] for f in w]
    low = sum(1 for s in secs if s < 15)
    r = rows[i]
    out.append(dict(t=b, flips=fl / dur, gap=gap, low=low, n=len(w), **{k: r[k] for k in ('rd', 'pm', 'pio', 'avail', 'swap', 'gtt', 'rss', 'mrss')}))
print(' t_end flips/s maxgap lowsec/n read_MiB psi_m psi_io avail swap gtt rss mrss')
for o in out:
    print('%6d %6.1f %7.0f %3d/%3d %6d %5.2f %6.2f %5d %5d %6d %5s %4d' % (o['t'], o['flips'], o['gap'], o['low'], o['n'], o['rd'], o['pm'], o['pio'], o['avail'], o['swap'], o['gtt'], o['rss'], o['mrss']))
def r(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
sel = [o for o in out if 240 <= o['t'] <= 2220]
fl = [o['flips'] for o in sel]
for k in ('rd', 'pm', 'pio', 'avail', 'swap', 'mrss'):
    print('r(flips,%s)=%.2f' % (k, r(fl, [o[k] for o in sel])))
print('r(rd,pm)=%.2f r(rd,pio)=%.2f' % (r([o['rd'] for o in sel], [o['pm'] for o in sel]), r([o['rd'] for o in sel], [o['pio'] for o in sel])))
for lo, hi in ((0, 2000), (2000, 4000), (4000, 6000), (6000, 8000), (8000, 99999)):
    g = [o for o in sel if lo <= o['rd'] < hi]
    if g:
        print('reads %5d-%5d n=%2d flips %.1f frame_ms %.1f psi_m %.2f psi_io %.2f' % (lo, hi, len(g), st.mean(o['flips'] for o in g), 1000 / st.mean(o['flips'] for o in g), st.mean(o['pm'] for o in g), st.mean(o['pio'] for o in g)))
tot = sum(o['rd'] for o in sel)
print('total read in selection %.1f GiB over %d min = %.1f GiB/min' % (tot / 1024, len(sel), tot / 1024 / len(sel)))
A = [(o['rd'], 1000 / o['flips']) for o in sel]
n = len(A); mx = st.mean(a for a, _ in A); my = st.mean(b for _, b in A)
b = sum((x - mx) * (y - my) for x, y in A) / sum((x - mx) ** 2 for x, _ in A)
print('frame ms = %.1f + %.2f ms per GiB/min' % (my - b * mx, b * 1024))
