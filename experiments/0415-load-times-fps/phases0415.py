#!/usr/bin/env python3
# BC5 exp 0415: cut one load run into phases and say where each phase's time went. Laptop, offline.
# Input: <tag>-loadstat.txt (the emulator's KYTY_BC5_LOAD_STAT file) and, if present, <tag>-col.txt (col0415.py).
# The phases, by rule (README section 4); times are CLOCK_MONOTONIC seconds from the first counter line:
#   P1 movies       from the first counter line to the first second under 24 flips that starts two such seconds, after 8 s
#   P2 menu load    to the first second of 30 flips or more that starts a run of three
#   P3 start screen to the first key
#   P4 menus        to the third key (Continue)
#   P5 save load    to the first three seconds in a row with 20 flips or more and no command buffer outstanding at the
#                   second's end, at least 3 s after the key
#   P6 play         the rest
# A phase the run did not reach is printed as "not reached" (never 0).
# usage: phases0415.py <raw dir> <tag> [--tsv]
import gzip
import json
import os
import sys


def parse_stat(path):
    rows, marks = [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split()
        if not p:
            continue
        if p[0] == 's':
            r = {'c': {}}
            for x in p[1:]:
                k, _, v = x.partition('=')
                if ',' in v:
                    a = v.split(',')
                    if len(a) == 4:
                        r['c'][k] = tuple(int(y) for y in a)
                elif k in ('mono_ns', 'jt_us', 'apr_out'):
                    r[k] = int(v)
            if 'mono_ns' in r and 'flip' in r['c']:
                rows.append(r)
        elif p[0] == 'mark':
            d = dict(x.partition('=')[::2] for x in p[1:3])
            marks.append((int(d.get('mono_ns', 0)), ' '.join(p[3:])))
    return rows, marks


def cut(rows, marks):
    t0 = rows[0]['mono_ns']
    t = [(r['mono_ns'] - t0) / 1e9 for r in rows]
    fl = [0] + [rows[i]['c']['flip'][0] - rows[i - 1]['c']['flip'][0] for i in range(1, len(rows))]
    n = len(rows)
    keys = [(m - t0) / 1e9 for m, text in marks if text.startswith('key press')]
    b = {}

    def first(lo, pred):
        for i in range(max(lo, 1), n):
            if pred(i):
                return i
        return None

    i1 = first(0, lambda i: t[i] >= 8 and i + 1 < n and fl[i] < 24 and fl[i + 1] < 24)
    b['P1 movies'] = (0, i1)
    i2 = first(i1, lambda i: i + 2 < n and min(fl[i], fl[i + 1], fl[i + 2]) >= 30) if i1 is not None else None
    b['P2 menu load'] = (i1, i2)

    def at(sec):
        return first(0, lambda i: t[i] >= sec)

    k1 = at(keys[0]) if len(keys) >= 1 else None
    k3 = at(keys[2]) if len(keys) >= 3 else None
    b['P3 start screen'] = (i2, k1)
    b['P4 menus'] = (k1, k3)
    i5 = None
    if k3 is not None:
        i5 = first(k3, lambda i: t[i] >= keys[2] + 3 and i + 2 < n and min(fl[i], fl[i + 1], fl[i + 2]) >= 20 and
                   max(rows[i].get('apr_out', 0), rows[i + 1].get('apr_out', 0), rows[i + 2].get('apr_out', 0)) == 0)
    b['P5 save load'] = (k3, i5)
    b['P6 play'] = (i5, n - 1 if i5 is not None else None)
    return t, fl, keys, b


def col_rows(path):
    rows, hz = [], 100
    if not os.path.exists(path):
        return rows, hz
    op = gzip.open if path.endswith('.gz') else open
    for line in op(path, 'rt', encoding='utf-8', errors='replace'):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if 'header' in r:
            hz = r.get('hz', 100)
        elif 'mono' in r:
            rows.append(r)
    return rows, hz


def col_delta(crows, hz, m0, m1):
    a = [r for r in crows if m0 <= r['mono'] <= m1]
    if len(a) < 2:
        return None
    x, y = a[0], a[-1]
    dt = y['mono'] - x['mono']
    out = {'dt': dt}
    thr = {}
    for tid, e in y.get('thr', {}).items():
        e0 = x.get('thr', {}).get(tid)
        if e0 is None:
            continue
        thr[e['n']] = thr.get(e['n'], 0.0) + ((e['u'] + e['s']) - (e0['u'] + e0['s'])) / hz
    out['thr'] = sorted(thr.items(), key=lambda kv: -kv[1])
    out['cpu_s'] = sum(thr.values())
    if 'io' in x and 'io' in y:
        out['read_asked_mib'] = (y['io']['rchar'] - x['io']['rchar']) / 2**20
        out['read_disk_mib'] = (y['io']['read_bytes'] - x['io']['read_bytes']) / 2**20
    if 'vm' in x and 'vm' in y:
        out['vm'] = {k: y['vm'][k] - x['vm'][k] for k in y['vm'] if k in x['vm']}
    if 'mem_kb' in x and 'mem_kb' in y:
        out['avail_mib'] = (x['mem_kb'].get('MemAvailable', 0) / 1024, min(r['mem_kb'].get('MemAvailable', 0) for r in a if 'mem_kb' in r) / 1024)
    g0, g1 = x.get('gpu_ns'), y.get('gpu_ns')
    if g0 is not None and g1 is not None:
        tot = 0
        for cid, eng in g1.items():
            for name, v in eng.items():
                tot += v - g0.get(cid, {}).get(name, v)
        out['gpu_s'] = tot / 1e9
    for k in ('kcompactd0_ticks', 'kswapd0_ticks'):
        if k in x and k in y:
            out[k[:-6] + '_s'] = (y[k] - x[k]) / hz
    out['rsync'] = max(r.get('rsync', 0) for r in a)
    return out


def main():
    raw, tag = sys.argv[1], sys.argv[2]
    rows, marks = parse_stat(os.path.join(raw, tag + '-loadstat.txt'))
    if len(rows) < 10:
        print('%s: %d counter lines: not enough to cut' % (tag, len(rows)))
        return 1
    t, fl, keys, b = cut(rows, marks)
    crows, hz = col_rows(os.path.join(raw, tag + '-col.txt'))
    print('%s: %d counter lines over %.0f s; keys at %s s; first line at journal t %.1f s' % (
        tag, len(rows), t[-1], ', '.join('%.1f' % k for k in keys) or 'none', rows[0].get('jt_us', 0) / 1e6))
    for name, (i0, i1) in b.items():
        if i0 is None or i1 is None or i1 <= i0:
            print('\n== %s: not reached' % name)
            continue
        dur = t[i1] - t[i0]
        flips = rows[i1]['c']['flip'][0] - rows[i0]['c']['flip'][0]
        print('\n== %s: %.1f s (%.1f to %.1f), %d flips, %.1f flips/s' % (name, dur, t[i0], t[i1], flips, flips / dur))
        lines = []
        for k, v1 in rows[i1]['c'].items():
            v0 = rows[i0]['c'].get(k, (0, 0, 0, 0))
            dn, dns, di = v1[0] - v0[0], v1[1] - v0[1], v1[3] - v0[3]
            if k == 'flip' or (dn == 0 and dns == 0):
                continue
            mx = max(rows[j]['c'].get(k, (0, 0, 0, 0))[2] for j in range(i0 + 1, i1 + 1))
            lines.append((dns, '   %-17s n %9d  time %8.3f s (%5.1f %% of the phase)  mean %9.1f us  longest %8.2f ms  items %d' % (
                k, dn, dns / 1e9, 100.0 * dns / 1e9 / dur, (dns / dn / 1e3) if dn else 0.0, mx / 1e6, di)))
        for _, s in sorted(lines, key=lambda x: -x[0]):
            print(s)
        if crows:
            c = col_delta(crows, hz, rows[i0]['mono_ns'] / 1e9, rows[i1]['mono_ns'] / 1e9)
            if c is None:
                print('   outside: no collector rows in the phase')
                continue
            print('   outside: emulator CPU %.1f s = %.2f CPUs; %s' % (c['cpu_s'], c['cpu_s'] / c['dt'], ', '.join('%s %.0f %%' % (n, 100 * v / c['dt']) for n, v in c['thr'][:8])))
            extra = []
            if 'gpu_s' in c:
                extra.append('GPU engines %.1f s (%.0f %%)' % (c['gpu_s'], 100 * c['gpu_s'] / c['dt']))
            if 'read_asked_mib' in c:
                extra.append('reads asked %.0f MiB, from disk %.0f MiB' % (c['read_asked_mib'], c['read_disk_mib']))
            if 'avail_mib' in c:
                extra.append('available %.0f MiB at the start, lowest %.0f' % c['avail_mib'])
            if 'vm' in c:
                v = c['vm']
                extra.append('major faults %d, reclaim scanned %d kswapd + %d direct pages, compaction stalls %d' % (
                    v.get('pgmajfault', 0), v.get('pgscan_kswapd', 0), v.get('pgscan_direct', 0), v.get('compact_stall', 0)))
            for k in ('kcompactd0_s', 'kswapd0_s'):
                if k in c:
                    extra.append('%s %.1f s' % (k[:-2], c[k]))
            extra.append('rsync seen' if c['rsync'] else 'no rsync')
            print('   outside: ' + '; '.join(extra))
    return 0


sys.exit(main())
