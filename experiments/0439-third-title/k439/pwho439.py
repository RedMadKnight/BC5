# BC5 exp 0439: who writes the labels of a kept dcb's piece waits (read-only, over a capture's files).
#   python3 -I pwho439.py <capture gc dir> <dcb number>
# For each memory WAIT_REG_MEM in the dcb's pieces (pa439-dcb-<n>-piece-<k>-<dw>.bin): label, function, reference, and
# who writes the label among: the same piece before the wait (kept by the filter), the dcb's own pieces (earlier or
# later), and the ring's job files (pa439-job-<n>-<kind>-<dw>.bin, top level) by WRITE_DATA (0x37), RELEASE_MEM (0x49),
# EVENT_WRITE_EOP (0x47) or ATOMIC_MEM (0x1e). Labels nobody in these writes are "not in these buffers" (the CPU, the
# host, or a job outside the ring).
import glob
import re
import struct
import sys

d, n = sys.argv[1], sys.argv[2]


def words(fn):
    b = open(fn, 'rb').read()
    return struct.unpack('<%dI' % (len(b) // 4), b[:len(b) // 4 * 4])


def packets(w):
    i = 0
    while i < len(w):
        h = w[i]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            ln = 1 if c == 0x3fff else c + 2
        if i + ln > len(w):
            break
        yield i, (h >> 8) & 0xff if t == 3 else None, w[i:i + ln]
        i += ln


def addr(lo, hi):
    return (lo & ~3) | ((hi & 0xffff) << 32)


def writes(p, op):
    if op == 0x37 and len(p) >= 5 and ((p[1] >> 8) & 0xf) in (2, 5):
        return addr(p[2], p[3])
    if op == 0x49 and len(p) >= 7:
        return addr(p[3], p[4])
    if op == 0x47 and len(p) >= 5:
        return addr(p[2], p[3])
    if op == 0x1e and len(p) >= 4:
        return addr(p[2], p[3])
    return None


pieces = {}
for fn in glob.glob('%s/pa439-dcb-%s-piece-*.bin' % (d, n)):
    k = int(re.search(r'-piece-(\d+)-', fn).group(1))
    pieces[k] = words(fn)
jobs = {}
for fn in glob.glob('%s/pa439-job-*.bin' % d):
    m = re.search(r'pa439-job-(\d+)-(\w+)-(\d+)\.bin', fn)
    jobs['#%s %s %s' % m.groups()] = words(fn)
wr = {}  # label -> [(where, position)]
for k, w in pieces.items():
    for i, op, p in packets(w):
        a = writes(p, op)
        if a is not None:
            wr.setdefault(a, []).append(('dcb piece %d' % k, i))
for j, w in jobs.items():
    for i, op, p in packets(w):
        a = writes(p, op)
        if a is not None:
            wr.setdefault(a, []).append(('job ' + j, i))
rows = 0
for k in sorted(pieces):
    w = pieces[k]
    own = []
    for i, op, p in packets(w):
        a = writes(p, op)
        if a is not None:
            own.append(a)
        if op == 0x3c and len(p) >= 7 and (p[1] >> 4) & 1:
            a = addr(p[2], p[3])
            fate = 'top level' if k == 0 else ('kept (written earlier in its piece)' if a in own else 'DROPPED by the piece filter')
            ws = wr.get(a, [])
            later = [x for x in ws if x[0] == 'dcb piece %d' % k and x[1] > i] + [x for x in ws if x[0].startswith('dcb piece') and int(x[0].split()[-1]) > k]
            earlier = [x for x in ws if x[0].startswith('dcb piece') and int(x[0].split()[-1]) < k]
            other = [x for x in ws if x[0].startswith('job')]
            print('piece %2d dw %4d 0x%010x fn %d ref 0x%x: %s | writers: earlier dcb %s; later dcb %s; ring jobs %s' % (
                k, i, a, p[1] & 7, p[4], fate, [x[0] for x in earlier][:3] or '-', [x[0] for x in later][:3] or '-',
                sorted(set(x[0] for x in other))[:4] or '-'))
            rows += 1
print('%d memory waits in %d pieces; %d ring jobs read' % (rows, len(pieces), len(jobs)))
