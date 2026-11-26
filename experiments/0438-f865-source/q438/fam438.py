import os, re, struct, sys
FAM = {0x400202d00: 'd00', 0x400202d40: 'd40', 0x400202d80: 'd80', 0x400202dc0: 'dc0', 0x400203940: 'L3940', 0x400201d40: 'L1d40'}
def scan(path):
    b = open(path, 'rb').read(); d = struct.unpack('<%dI' % (len(b) // 4), b); i = 0; n = len(d); out = []
    while i < n:
        h = d[i]; t = h >> 30
        if t == 3:
            c = (h >> 16) & 0x3fff; ln = 1 if c == 0x3fff else c + 2; op = (h >> 8) & 0xff
            if op == 0x49 and ln >= 8 and i + 6 < n:
                a = (d[i+3] & ~3) | ((d[i+4] & 0xffff) << 32)
                if a in FAM: out.append((i, 'W', FAM[a], d[i+5]))
            elif op == 0x37 and ln >= 5 and i + 4 < n:
                a = (d[i+2] & ~3) | ((d[i+3] & 0xffff) << 32)
                if a in FAM: out.append((i, 'W', FAM[a], d[i+4]))
            elif op in (0x3c, 0x93) and ln >= 6 and i + 5 < n:
                a = (d[i+2] & ~3) | ((d[i+3] & 0xffff) << 32)
                if a in FAM: out.append((i, 'w', FAM[a], d[i+4]))
        elif t == 0: ln = ((h >> 16) & 0x3fff) + 2
        else: ln = 1
        i += ln
    return out
for D in sys.argv[1:]:
    print('==', os.path.basename(os.path.dirname(D)))
    fs = sorted((f for f in os.listdir(D) if f.startswith('ib-')), key=lambda f: int(re.match(r'ib-0*(\d+)', f).group(1)))
    for f in fs:
        ev = scan(os.path.join(D, f))
        if ev:
            m = re.match(r'ib-0*(\d+)-(\w+)-(\d+)', f)
            print('#%s %s %s: ' % m.groups() + '; '.join('%s%s%s=%#x@%d' % ('' , k, nm, v, pos) for pos, k, nm, v in ev))
