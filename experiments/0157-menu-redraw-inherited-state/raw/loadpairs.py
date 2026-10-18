#!/usr/bin/env python3
# Experiment 0157: for every journaled layer draw, the LOAD_CONTEXT_REG_INDEX pair table loaded last
# before it: which pair sets CB_BLEND0_CONTROL (ctx 0x1e0) and where it sits; if the CP counted dwords
# instead of pairs, pairs at index >= ceil(n/2) would never be applied. Per buffer: flagged?, the number of
# layer draws whose blend pair would be lost, and the distinct (n, index) seen.
# Usage: loadpairs.py <direct.log> <T0 epoch> <flagged shots,...> [detail buf,...]
import sys, re, collections
log, T0 = sys.argv[1], float(sys.argv[2])
flag = set(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else set()
detail = set(int(x) for x in sys.argv[4].split(",")) if len(sys.argv) > 4 else set()
rl = re.compile(r"^load table buf (\d+) at (\d+): op (\w+) dw1 (\w+) dw3 (\w+) (pairs|span) x(\d+) at ([0-9a-f]+):(.*)$")
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) .* \| ps ([0-9a-f]+) es")
rb = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall ([\d.]+) \| .* blend0 (\w+) cc")
loads = collections.defaultdict(list); draws = collections.defaultdict(list); wall = {}; blend = {}
for line in open(log, errors="replace"):
    m = rl.match(line)
    if m:
        b, off, op, n = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(7))
        pairs = [(int(x.split(":")[0], 16), x.split(":")[1]) for x in m.group(9).split() if ":" in x] if m.group(6) == "pairs" else []
        loads[b].append((off, op, n, m.group(8), pairs)); continue
    m = rm.match(line)
    if m:
        b, off = int(m.group(1)), int(m.group(3))
        draws[b].append((off, m.group(4).split()[0], int(m.group(6)), m.group(8))); continue
    m = rb.match(line)
    if m:
        b, off = int(m.group(1)), int(m.group(2))
        wall.setdefault(b, float(m.group(4)) - T0); blend[(b, off)] = m.group(5)
tot_lost = collections.Counter(); tot_draws = collections.Counter(); combos = collections.Counter()
for b in sorted(draws):
    w = wall.get(b, 0); k = int(w // 2) + 1; fl = [s for s in (k, k + 1) if s in flag]
    lds = sorted(loads.get(b, []))
    lost = 0; nl = 0; notes = []
    for off, hdr, wdt, ps in draws[b]:
        if wdt <= 2048 or not hdr.startswith("c003"): continue  # layer draws (DRAW_INDEX_OFFSET_2) only
        nl += 1
        # the last context pair table before the draw that names 0x1e0
        last = None
        for l in lds:
            if l[0] >= off: break
            if l[1] == "9f" and any(o == 0x1e0 for o, _ in l[4]): last = l
        if last is None:
            notes.append("at %d: no 0x1e0 table before" % off); continue
        idx = [i for i, (o, _) in enumerate(last[4]) if o == 0x1e0][0]
        n = last[2]; v = last[4][idx][1]
        would_lose = idx >= (n + 1) // 2
        combos[(n, idx, would_lose)] += 1
        if would_lose: lost += 1
        if b in detail: notes.append("at %d: table at %d x%d, 0x1e0 is pair %d = %s (tracker %s)%s" % (off, last[0], n, idx, v, blend.get((b, off)), " LOST?" if would_lose else ""))
    key = "flagged" if fl else "clean"
    tot_lost[key] += lost; tot_draws[key] += nl
    print("buf %3d +%7.2f s%-3d %-14s layer draws %2d, blend pair in the lost half: %2d  %s" % (b, w, k, ("FLAGGED " + ",".join(map(str, fl))) if fl else "", nl, lost, "; ".join(notes[:8])))
print("totals: flagged buffers: %d of %d layer draws would lose their blend pair; clean: %d of %d" % (tot_lost["flagged"], tot_draws["flagged"], tot_lost["clean"], tot_draws["clean"]))
print("(n pairs, index of 0x1e0, lost?) combos:", combos.most_common(12))
