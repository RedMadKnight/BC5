import gzip, re, sys
from collections import defaultdict
F = re.compile(r'^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip; game thread inside the host ([0-9.]+) ms \(sync ([0-9.]+), hints ([0-9.]+), prepare ([0-9.]+), list ([0-9.]+), cs ([0-9.]+), fence ([0-9.]+), cap ([0-9.]+), label waits ([0-9.]+), event waits ([0-9.]+)\), at the flip ([0-9.]+), outside ([0-9.]+); GPU busy ([0-9.]+) ms in (\d+) jobs')
names = ['ms','host','sync','hints','prepare','list','cs','fence','cap','label','event','flip','outside','gpu']
T = re.compile(r'probe ([0-9.]+) ms, anon sync ([0-9.]+), direct sync ([0-9.]+) \(views ([0-9.]+); (\d+) full, (\d+) fast; scan ([0-9.]+), merge ([0-9.]+), drain ([0-9.]+) in (\d+), maps ([0-9.]+)')
C = re.compile(r'copy ([0-9.]+)')
for p in sys.argv[1:]:
    cls = defaultdict(lambda: defaultdict(float)); n = defaultdict(int); ts = [0.0]*8; drn = 0; drmax = 0; nomatch = 0
    over = defaultdict(lambda: [0, 0.0, 0.0]); last_t = 0
    for line in gzip.open(p, 'rt', errors='replace'):
        if line.startswith('frame profile'):
            m = F.match(line)
            if not m: nomatch += 1; continue
            v = dict(zip(names, map(float, m.groups()[1:15]))); last_t = float(m.group(1))
            c = C.search(line); v['copy'] = float(c.group(1)) if c else 0.0
            k = 'gap>100' if v['ms'] > 100 else ('50-100' if v['ms'] > 50 else '<=50')
            n[k] += 1
            for a, b in v.items(): cls[k][a] += b
            for a in ('sync', 'prepare', 'copy', 'cs', 'fence', 'label', 'event', 'flip', 'hints', 'cap', 'outside'):
                if v[a] > 20:
                    o = over[a]; o[0] += 1; o[1] += v[a]; o[2] = max(o[2], v[a])
        elif line.startswith('timing split'):
            m = T.search(line)
            if m:
                g = m.groups()
                for i, j in enumerate((0, 1, 2, 3, 6, 7, 8, 10)): ts[i] += float(g[j])
                drn += int(g[9]); drmax = max(drmax, float(g[8]))
    import os; print('==', os.path.basename(p), 'last t %.0f s, unparsed frame lines %d' % (last_t, nomatch))
    for k in ('<=50', '50-100', 'gap>100'):
        c = cls[k]
        if not n[k]: continue
        print('  %-8s %6d frames %7.1f s | host %.1f s: sync %.1f hints %.1f prepare %.1f (copy %.1f) cs %.1f fence %.1f cap %.1f label %.1f event %.1f | flip-drain %.1f | outside %.1f | GPU busy %.1f' % (
            k, n[k], c['ms']/1e3, c['host']/1e3, c['sync']/1e3, c['hints']/1e3, c['prepare']/1e3, c['copy']/1e3, c['cs']/1e3, c['fence']/1e3, c['cap']/1e3, c['label']/1e3, c['event']/1e3, c['flip']/1e3, c['outside']/1e3, c['gpu']/1e3))
    print('  frames with a part over 20 ms: ' + '; '.join('%s %d (%.1f s, max %.0f ms)' % (a, o[0], o[1]/1e3, o[2]) for a, o in sorted(over.items(), key=lambda x: -x[1][1])))
    print('  timing split sums [s]: probe %.1f, anon sync %.1f, direct sync %.1f (views %.1f, scan %.1f, merge %.1f, drain %.1f in %d drains, largest window %.1f ms, maps %.1f)' % (
        ts[0]/1e3, ts[1]/1e3, ts[2]/1e3, ts[3]/1e3, ts[4]/1e3, ts[5]/1e3, ts[6]/1e3, drn, drmax, ts[7]/1e3))
