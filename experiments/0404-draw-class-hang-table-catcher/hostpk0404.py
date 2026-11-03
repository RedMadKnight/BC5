import sys
lines = open(sys.argv[1]).read().split('\n')
s = next(i for i, l in enumerate(lines) if l.startswith('IB #0'))
ib = []
for l in lines[s + 1:]:
    if not l.startswith('0x'): break
    ib.append(int(l, 16))
lo, hi = int(sys.argv[2]), int(sys.argv[3]); i = 0
while i < len(ib):
    h = ib[i]; t = h >> 30; n = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff; n = 1 if c == 0x3fff else c + 2
    if lo <= i <= hi:
        print('%5d t%d op 0x%02x len %3d | %s' % (i, t, (h >> 8) & 0xff, n, ' '.join('%08x' % x for x in ib[i+1:i+min(n, 10)])))
    i += n
