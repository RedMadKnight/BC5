#!/usr/bin/env python3
# BC5 exp 0415: the outside collector of a load run (col0415b: also the GPU engine time of the desktop's other clients). Reads /proc and /sys only (no root, no ptrace, no write outside
# <out file>). One JSON line a second with CLOCK_MONOTONIC: memory and reclaim counters, pressure, the NVMe's read
# counters, the emulator's read counters and GPU engine time (fdinfo, one reading per drm client id), and per thread
# of the emulator: CPU ticks, time on the run queue and context switches. A value that could not be read is absent
# from the line (never 0).
# usage (on the box, host): col0415.py <out file> <max seconds>
import json
import os
import sys
import time

OUT, MAX = sys.argv[1], int(sys.argv[2])
VM = ('pgscan_kswapd', 'pgscan_direct', 'pgsteal_kswapd', 'pgsteal_direct', 'pgmajfault', 'pgfault', 'pswpin', 'pswpout',
      'compact_stall', 'compact_migrate_scanned', 'allocstall_normal', 'allocstall_movable', 'workingset_refault_file',
      'workingset_refault_anon', 'pgpgin')


def rd(path):
    try:
        with open(path, 'rb') as f:
            return f.read().decode('ascii', 'replace')
    except OSError:
        return None


def find(prefix):
    for d in os.listdir('/proc'):
        if d.isdigit():
            c = rd('/proc/%s/comm' % d)
            if c is not None and c.strip().startswith(prefix):
                return int(d)
    return None


def kv(text, keys, sep=None):
    r = {}
    if text is None:
        return r
    for line in text.splitlines():
        p = line.replace(':', ' ').split(sep)
        if len(p) >= 2 and p[0] in keys:
            try:
                r[p[0]] = int(p[1])
            except ValueError:
                pass
    return r


def psi(name):
    t = rd('/proc/pressure/' + name)
    r = {}
    if t is None:
        return r
    for line in t.splitlines():
        p = line.split()
        for x in p[1:]:
            k, _, v = x.partition('=')
            if k == 'total':
                r[p[0] + '_us'] = int(v)
            elif k == 'avg10':
                r[p[0] + '_avg10'] = float(v)
    return r


def disk():
    t = rd('/proc/diskstats')
    r = {}
    if t is None:
        return r
    for line in t.splitlines():
        p = line.split()
        if len(p) >= 14 and p[2].startswith('nvme') and p[2].endswith('n1'):
            r[p[2]] = {'reads': int(p[3]), 'sectors_read': int(p[5]), 'ms_reading': int(p[6]), 'in_flight': int(p[11]), 'ms_io': int(p[12]), 'ms_weighted': int(p[13])}
    return r


def gpu(pid):
    seen = {}
    try:
        fds = os.listdir('/proc/%d/fdinfo' % pid)
    except OSError:
        return None
    for fd in fds:
        t = rd('/proc/%d/fdinfo/%s' % (pid, fd))
        if t is None or 'drm-client-id' not in t:
            continue
        cid, eng = None, {}
        for line in t.splitlines():
            k, _, v = line.partition(':')
            v = v.strip()
            if k == 'drm-client-id':
                cid = v
            elif k.startswith('drm-engine-') and v.endswith(' ns'):
                eng[k[11:]] = int(v[:-3])
        if cid is not None and cid not in seen:
            seen[cid] = eng
    return seen


def threads(pid):
    r = {}
    try:
        tids = os.listdir('/proc/%d/task' % pid)
    except OSError:
        return None
    for tid in tids:
        base = '/proc/%d/task/%s/' % (pid, tid)
        st = rd(base + 'stat')
        if st is None:
            continue
        rp = st.rfind(')')
        f = st[rp + 2:].split()
        e = {'n': st[st.find('(') + 1:rp], 'u': int(f[11]), 's': int(f[12]), 'minflt': int(f[7]), 'majflt': int(f[9]), 'cpu': int(f[36])}
        ss = rd(base + 'schedstat')
        if ss is not None:
            p = ss.split()
            if len(p) >= 3:
                e['run_ns'], e['wait_ns'], e['slices'] = int(p[0]), int(p[1]), int(p[2])
        sw = kv(rd(base + 'status'), ('voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches'))
        if 'voluntary_ctxt_switches' in sw:
            e['vol'] = sw['voluntary_ctxt_switches']
        if 'nonvoluntary_ctxt_switches' in sw:
            e['invol'] = sw['nonvoluntary_ctxt_switches']
        r[tid] = e
    return r


def ticks(pid):
    st = rd('/proc/%d/stat' % pid) if pid else None
    if st is None:
        return None
    f = st[st.rfind(')') + 2:].split()
    return int(f[11]) + int(f[12])


def main():
    t0 = time.monotonic()
    pid = None
    while pid is None and time.monotonic() - t0 < 120:
        pid = find('kyty_emulator')
        if pid is None:
            time.sleep(0.25)
    with open(OUT, 'a', buffering=1) as out:
        out.write(json.dumps({'header': 1, 'pid': pid, 'hz': os.sysconf('SC_CLK_TCK'), 'mono': time.monotonic(), 'wall': time.time(),
                              'exe': os.readlink('/proc/%d/exe' % pid) if pid else None}) + '\n')
        if pid is None:
            return
        kc, ks = find('kcompactd0'), find('kswapd0')
        others = {n: find(n) for n in ('kwin_wayland', 'plasmashell', 'Xwayland')}  # col0415b: the other clients of the GPU
        nxt = time.monotonic()
        while time.monotonic() - t0 < MAX and os.path.isdir('/proc/%d' % pid):
            row = {'mono': time.monotonic()}
            mi = kv(rd('/proc/meminfo'), ('MemAvailable', 'MemFree', 'SwapFree', 'Cached', 'Shmem', 'Dirty', 'Unevictable'))
            if mi:
                row['mem_kb'] = mi
            vm = kv(rd('/proc/vmstat'), VM)
            if vm:
                row['vm'] = vm
            for n in ('memory', 'io', 'cpu'):
                p = psi(n)
                if p:
                    row['psi_' + n] = p
            d = disk()
            if d:
                row['disk'] = d
            io = kv(rd('/proc/%d/io' % pid), ('rchar', 'read_bytes', 'syscr', 'wchar', 'write_bytes'))
            if io:
                row['io'] = io
            g = gpu(pid)
            if g is not None:
                row['gpu_ns'] = g
            th = threads(pid)
            if th is not None:
                row['thr'] = th
            for name, p in (('kcompactd0', kc), ('kswapd0', ks)):
                v = ticks(p)
                if v is not None:
                    row[name + '_ticks'] = v
            go = {}
            for n, opid in others.items():
                if opid is not None:
                    g2 = gpu(opid)
                    if g2:
                        go[n] = sum(v for eng in g2.values() for v in eng.values())
            if go:
                row['gpu_other_ns'] = go  # col0415b: summed engine time of each other client (all its engines)
            la = rd('/proc/loadavg')
            if la is not None:
                row['load1'] = float(la.split()[0])
            row['rsync'] = 1 if find('rsync') is not None else 0
            out.write(json.dumps(row, separators=(',', ':')) + '\n')
            nxt += 1.0
            time.sleep(max(0.0, nxt - time.monotonic()))


main()
