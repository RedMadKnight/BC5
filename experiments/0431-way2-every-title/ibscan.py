import sys
f, start, want = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
L = open(f, 'rb').read().split(b'\n')
dw = []
for x in L[start:start+want]:
    x = x.strip()
    if not x.startswith(b'0x'): break
    dw.append(int(x, 16))
print("dwords", len(dw))
consumed = int(sys.argv[4], 16) if len(sys.argv) > 4 else None
names = {0x3c:'WAIT_REG_MEM',0x93:'WAIT_REG_MEM64',0x49:'RELEASE_MEM',0x46:'EVENT_WRITE',0x15:'DISPATCH_DIRECT',0x16:'DISPATCH_INDIRECT',0x3f:'INDIRECT_BUFFER',0x37:'WRITE_DATA',0x58:'ACQUIRE_MEM',0x50:'DMA_DATA',0x10:'NOP',0x28:'CONTEXT_CONTROL',0x12:'CLEAR_STATE',0x2d:'DRAW_INDEX_AUTO',0x27:'DRAW_INDEX_2',0x38:'DRAW_INDEX_INDIRECT_MULTI', 0x2c:'DRAW_INDIRECT_MULTI',0x22:'COND_EXEC',0x42:'PFP_SYNC_ME',0x45:'COND_WRITE'}
i = 0; pk = []
while i < len(dw):
    h = dw[i]; t = h >> 30
    if t == 3:
        op = (h >> 8) & 0xff; n = ((h >> 16) & 0x3fff) + 2
        pk.append((i, op, dw[i:i+min(n, 8)])); i += n
    elif t == 2: i += 1
    else:
        pk.append((i, -1, [h])); i += 1
waits = [p for p in pk if p[1] in (0x3c, 0x93)]
print("packets", len(pk), "waits", len(waits))
if consumed is not None:
    near = [p for p in pk if consumed - 400 <= p[0] <= consumed + 60]
    for p in near:
        if p[1] in names and p[1] not in (0x10,):
            print("%7d %-24s %s" % (p[0], names.get(p[1], hex(p[1])), ' '.join('%08x' % d for d in p[2])))
from collections import Counter
c = Counter(p[1] for p in pk); print(sorted(((hex(k) if k>=0 else 'raw'), v) for k, v in c.items()))
c0 = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0
for p in pk:
    if c0 - 120 <= p[0] <= c0 + 40:
        print("%7d %-24s %s" % (p[0], names.get(p[1], hex(p[1])), ' '.join('%08x' % d for d in p[2])))
