import sys
lines = open(sys.argv[1]).read().split('\n')
s = next(i for i, l in enumerate(lines) if l.startswith('IB #0'))
ib = []
for l in lines[s + 1:]:
    if not l.startswith('0x'): break
    ib.append(int(l, 16))
pk, i = [], 0
while i < len(ib):
    h = ib[i]; t = h >> 30; n = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff; n = 1 if c == 0x3fff else c + 2
    pk.append((i, t, (h >> 8) & 0xff, n, h)); i += n
want = [0x42, 0x37, 0x45, 0x45, 0x37, 0x11, 0x76, 0x63]   # PFP history, newest first
wantlen = {0x76: 19, 0x63: 5}
real = [p for p in pk if p[1] == 3 and p[2] != 0x10]       # type-3, NOPs left out
for k in range(len(real)):
    if real[k][2] != 0x42: continue
    back = real[k - 7:k + 1][::-1]
    if [p[2] for p in back] == want and all(p[3] == wantlen.get(p[2], p[3]) for p in back):
        nxt = real[k + 1:k + 3]
        print('match: PFP_SYNC_ME at host', real[k][0], 'then', ['op 0x%02x at %d' % (p[2], p[0]) for p in nxt])
print('host IB', len(ib), 'dw; fetched to', len(ib) - int(sys.argv[2], 16))
