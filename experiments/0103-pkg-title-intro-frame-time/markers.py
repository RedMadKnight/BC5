# Per dumped buffer: the game's pass-name markers (SET_UCONFIG 0x342 first dword + WRITE_DATA to
# 0xc343), label waits (WAIT_REG_MEM / WAIT_REG_MEM64 with address), dispatches and draws.
import struct, sys, os, re
D = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 40
OPS = {0x3c: "WAIT_REG_MEM", 0x93: "WAIT_REG_MEM64", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT",
       0x2d: "DRAW_INDEX_AUTO", 0x27: "DRAW_INDEX_2", 0x3f: "INDIRECT_BUFFER", 0x50: "DMA_DATA",
       0x22: "COND_EXEC", 0x49: "RELEASE_MEM"}
for f in sorted(os.listdir(D)):
    m = re.match(r"ib-(\d+)-(\w+)-(\d+)\.bin", f)
    if not m or not (lo <= int(m.group(1)) < hi): continue
    d = open(os.path.join(D, f), "rb").read(); ib = struct.unpack("<%dI" % (len(d) // 4), d)
    out = []; i = 0; pend = b""
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3:
            op = (h >> 8) & 0xff; body = ib[i + 1:i + n]
            if op == 0x79 and body and body[0] == 0x342 and len(body) >= 2:
                v = body[1]
                if len(body) >= 3 and (v >> 24) in (0xc1,):
                    pend = struct.pack("<I", body[2])
            elif op == 0x37 and len(body) >= 3 and body[1] == 0xc343:
                s = (pend + struct.pack("<%dI" % (len(body) - 3), *body[3:])).split(b"\0")[0]
                out.append('"%s"' % s.decode("ascii", "replace")); pend = b""
            elif op == 0x15 and len(body) >= 3:
                out.append("disp %dx%dx%d" % tuple(body[:3]))
            elif op == 0x93 and len(body) >= 3:
                out.append("wait64 %02x%08x" % (body[2] & 0xffff, body[1]))
            elif op == 0x3c and len(body) >= 3:
                out.append("wait %02x%08x=%x" % (body[2] & 0xffff, body[1], body[3] if len(body) > 3 else 0))
            elif op in (0x2d, 0x27):
                out.append("draw")
            elif op == 0x3f:
                out.append("ib %x%08x+%d" % (body[1] & 0xffff, body[0], body[2] & 0xfffff))
            elif op == 0x50:
                out.append("dma %d" % (body[5] & 0x1fffff if len(body) > 5 else -1))
        i += n
    # collapse repeats
    comp = [];
    for o in out:
        if comp and comp[-1][0] == o: comp[-1][1] += 1
        else: comp.append([o, 1])
    print("%s %s %s: %s" % (m.group(1), m.group(2), m.group(3), "  ".join(o if k == 1 else "%s x%d" % (o, k) for o, k in comp)))
