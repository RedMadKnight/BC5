#!/usr/bin/env python3
# Experiment 0194: summarise the draw journal of a run (BC5_DIRECT_DRAW_JOURNAL with edit0194.py's argument lines):
# per journaled buffer the draws by packet, colour target and pixel shader, and the indirect draws whose arguments
# exceed the CP check's limits ("cp-skip"), with their pixel shaders and targets.
# usage: python3 wj0194.py <direct.log> [buf]
import collections, re, sys

DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): (\S+)(.*?)\| rt0 (\S+) (\d+)x(\d+) info (\S+) mask (\S+) \| vp (\S+) at (\S+) \| ps (\S+) es (\S+) gs (\S+) cs (\S+)")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) base1 (\S+) \+0x(\S+)(.*)$")
draws, args = {}, {}
for line in open(sys.argv[1], errors="replace"):
    m = DRAW.match(line)
    if m:
        b, n, off = int(m[1]), int(m[2]), int(m[3])
        op = (int(m[4], 16) >> 8) & 0xff
        draws[(b, off)] = dict(buf=b, dwords=n, off=off, op=op, rt=m[6], w=int(m[7]), h=int(m[8]), info=m[9], mask=m[10], vp=m[11], ps=m[13], es=m[14], gs=m[15], cs=m[16])
        continue
    m = ARGS.match(line)
    if m:
        args[(int(m[1]), int(m[2]))] = line.rstrip("\n")
only = int(sys.argv[2]) if len(sys.argv) > 2 else None
bufs = sorted({d["buf"] for d in draws.values()})
print(f"{len(draws)} draws/dispatches in {len(bufs)} buffers; {len(args)} indirect-argument lines")
for b in bufs:
    if only is not None and b != only:
        continue
    ds = [d for d in draws.values() if d["buf"] == b]
    ops = collections.Counter(f"{d['op']:02x}" for d in ds)
    print(f"\n== buf {b} ({ds[0]['dwords']} dwords): {len(ds)} packets: " + ", ".join(f"{k}x{v}" for k, v in sorted(ops.items())))
    rts = collections.Counter((d["rt"], d["w"], d["h"], d["info"]) for d in ds if d["op"] not in (0x15, 0x16))
    for (rt, w, h, info), c in rts.most_common(12):
        pss = collections.Counter(d["ps"] for d in ds if d["rt"] == rt and d["op"] not in (0x15, 0x16))
        print(f"  rt0 {rt} {w}x{h} info {info}: {c} draws, {len(pss)} pixel shaders (top: " + ", ".join(f"{p}x{n}" for p, n in pss.most_common(4)) + ")")
    sk = [(k, v) for k, v in args.items() if k[0] == b]
    nskip = [v for k, v in sk if "cp-skip" in v]
    print(f"  indirect draws with arguments: {len(sk)}; cp-skip: {len(nskip)}")
    for (bb, off), v in sk:
        if "cp-skip" in v or "over the CP limits" in v and not re.search(r", 0 over the CP limits", v):
            d = draws.get((bb, off), {})
            print(f"    at {off}: ps {d.get('ps')} rt0 {d.get('rt')} {d.get('w')}x{d.get('h')} | {v.split(': ', 1)[1][:260]}")
