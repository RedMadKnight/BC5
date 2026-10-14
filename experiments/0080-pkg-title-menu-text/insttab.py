# Summarise the instance-table window snapshots (F116 layout, TODO(verify)): 128-byte records,
# 3x4 float transform (dwords 0-11), object tree address >> 3 (12-13), root link (14), flags (15).
import struct, sys, glob, math, os
d = sys.argv[1]
for f in sorted(glob.glob(d + "/snap-*.bin"), key=os.path.getmtime):
    b = open(f, "rb").read()
    for off in (0x3c100, 0x36100):
        recs = []
        for k in range(0, 512):
            o = off + k * 128
            if o + 128 > len(b): break
            w = struct.unpack_from("<32I", b, o)
            if not any(w[:16]): continue
            fl = struct.unpack_from("<12f", b, o)
            addr = ((w[13] << 32) | w[12]) << 3
            bad = any(math.isnan(x) or abs(x) > 1e7 for x in fl)
            recs.append((k, addr, w[14], w[15], bad))
        if not recs: print(os.path.basename(f), hex(off), "empty"); continue
        flags = {}
        for r in recs: flags[hex(r[3])] = flags.get(hex(r[3]), 0) + 1
        addrs = sorted(set(hex(r[1] >> 24) for r in recs))
        print(os.path.basename(f), hex(off), "records", len(recs), "last index", recs[-1][0], "bad transforms", sum(r[4] for r in recs),
              "flags", dict(sorted(flags.items(), key=lambda x: -x[1])[:5]), "tree addr>>24", addrs[:8])
