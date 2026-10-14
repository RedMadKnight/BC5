# Copies in dumped command buffers: DMA_DATA (0x50; dword1 control, 2-3 source, 4-5 destination,
# 6 command with the byte count in bits 25:0 -- layout TODO(verify) against PAL's pm4 headers)
# and COPY_DATA (0x40). Prints per buffer kind the copies with their sizes, grouped by destination.
import glob, struct, sys, collections, os
d = sys.argv[1]
copies = collections.Counter(); first = {}
for f in sorted(glob.glob(d + "/ib-*.bin")):
    name = os.path.basename(f); kind = name.split("-")[2]
    b = open(f, "rb").read(); ib = struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4])
    i = 0
    while i < len(ib):
        h = ib[i]; t = h >> 30; c = (h >> 16) & 0x3fff
        n = 1 if t not in (0, 3) or c == 0x3fff else c + 2
        if t == 3 and i + n <= len(ib):
            op = (h >> 8) & 0xff
            if op == 0x50 and n >= 7:
                ctl, slo, shi, dlo, dhi, cmd = ib[i + 1:i + 7]
                src = slo | (shi << 32); dst = dlo | (dhi << 32); cnt = cmd & 0x3ffffff
                key = (kind, "DMA_DATA", hex(dst >> 20), "src_sel %d dst_sel %d" % ((ctl >> 29) & 3, (ctl >> 20) & 3))
                copies[key] += 1
                first.setdefault(key, (name, hex(src), hex(dst), cnt))
            elif op == 0x40 and n >= 6:
                ctl = ib[i + 1]; src = ib[i + 2] | (ib[i + 3] << 32); dst = ib[i + 4] | (ib[i + 5] << 32)
                key = (kind, "COPY_DATA", hex(dst >> 20), "src_sel %d dst_sel %d" % (ctl & 0xf, (ctl >> 8) & 0xf))
                copies[key] += 1
                first.setdefault(key, (name, hex(src), hex(dst), 0))
        i += n
for k, v in copies.most_common(40):
    print(v, k, first[k])
