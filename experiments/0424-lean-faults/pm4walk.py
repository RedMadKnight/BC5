"""BC5 exp 0424: walk the PM4 type-3 packets of an IB dumped in an amdgpu devcoredump (the "IB #n <va> <n> dw" section).
    python pm4walk.py <devcd.txt> [ib index]
Prints per packet class counts, every dispatch / draw with the program and user data in effect (SH registers as
SET_SH_REG set them in this IB), every INDIRECT_BUFFER, and every 64-bit pair (lo, hi) whose address falls in
[0x1113400000, 0x1120000000) (past the end of the FileSystem view up to RenderGpuWcLarge) or has bits above 40.
Register offsets (SH, from 0x2c00): COMPUTE_PGM_LO 0x20c, COMPUTE_USER_DATA_0..15 0x240-0x24f,
SPI_SHADER_PGM_LO_PS 0x08 / USER_DATA_PS 0x0c.., _GS 0x88 / 0x8c.., _HS 0x108 / 0x10c.. (patch 0001's comments citing
Mesa sid.h / gfx10.json). Opcodes: 0x15 DISPATCH_DIRECT, 0x16 DISPATCH_INDIRECT, 0x3f INDIRECT_BUFFER, 0x76 SET_SH_REG,
0x9b SET_SH_REG_INDEX, 0x27 DRAW_INDEX_2, 0x2d DRAW_INDEX_AUTO, 0x38 DRAW_INDEX_INDIRECT_MULTI, 0x2c DRAW_INDIRECT_MULTI
(TODO(verify) the draw opcodes against Mesa sid.h; they only label lines)."""
import sys, collections

path = sys.argv[1]; want = int(sys.argv[2]) if len(sys.argv) > 2 else 0
L = open(path, errors="replace").read().split("\n")
ibs = []
i = 0
while i < len(L):
    if L[i].startswith("IB #"):
        p = L[i].split(); va = int(p[2], 16); n = int(p[3])
        d = [int(x, 16) for x in L[i + 1:i + 1 + n]]
        ibs.append((va, d)); i += n
    i += 1
va, d = ibs[want]
print("IB #%d at 0x%x, %d dw" % (want, va, len(d)))
NAMES = {0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT", 0x27: "DRAW_INDEX_2", 0x2d: "DRAW_INDEX_AUTO",
         0x38: "DRAW_INDEX_INDIRECT_MULTI", 0x2c: "DRAW_INDIRECT_MULTI", 0x3f: "INDIRECT_BUFFER", 0x76: "SET_SH_REG",
         0x9b: "SET_SH_REG_INDEX", 0x69: "SET_CONTEXT_REG", 0x79: "SET_UCONFIG_REG", 0x37: "WRITE_DATA", 0x10: "NOP",
         0x3c: "WAIT_REG_MEM", 0x46: "EVENT_WRITE", 0x49: "RELEASE_MEM", 0x58: "ACQUIRE_MEM", 0x40: "COPY_DATA",
         0x5f: "LOAD_SH_REG", 0x63: "LOAD_SH_REG_INDEX", 0x50: "DMA_DATA", 0x28: "CONTEXT_CONTROL", 0x11: "SET_BASE",
         0x22: "COND_EXEC", 0x33: "INDEX_TYPE", 0x13: "INDEX_BASE", 0xa0: "SET_PREDICATION", 0x20: "SET_PREDICATION"}
sh = {}
cnt = collections.Counter()
lo, hi = 0x1113400000, 0x1120000000
def interesting(a):
    return lo <= a < hi
p = 0; nd = 0; events = []
while p < len(d):
    h = d[p]; t = h >> 30
    if t == 2: p += 1; cnt["type2"] += 1; continue
    if t != 3: cnt["type%d" % t] += 1; p += 1; continue
    op = (h >> 8) & 0xff; n = ((h >> 16) & 0x3fff) + 1; body = d[p + 1:p + 1 + n]
    cnt[NAMES.get(op, "op%02x" % op)] += 1
    if op in (0x76, 0x9b) and body:
        base = body[0] & 0xffff
        for k, v in enumerate(body[1:]): sh[base + k] = v
    if op == 0x3f and len(body) >= 3:
        events.append("%6d INDIRECT_BUFFER 0x%x size %d dw ctl 0x%x" % (p, body[0] | (body[1] & 0xffff) << 32, body[2] & 0xfffff, body[2]))
    if op in (0x15, 0x16):
        pg = ((sh.get(0x20c, 0) | (sh.get(0x20d, 0) & 0xff) << 32) << 8)
        ud = [sh.get(0x240 + k, 0) for k in range(16)]
        events.append("%6d %s pgm 0x%x ud %s%s" % (p, NAMES[op], pg, " ".join("%08x" % u for u in ud), (" dims %s" % body[:3]) if op == 0x15 else ""))
        nd += 1
    if op in (0x27, 0x2d, 0x38, 0x2c):
        pgp = (sh.get(0x08, 0) | (sh.get(0x09, 0) & 0xff) << 32) << 8; pgg = (sh.get(0x88, 0) | (sh.get(0x89, 0) & 0xff) << 32) << 8
        events.append("%6d %s ps 0x%x gs 0x%x" % (p, NAMES[op], pgp, pgg))
    # 64-bit pairs inside the body
    for k in range(len(body) - 1):
        a = body[k] | body[k + 1] << 32
        if interesting(a) and body[k + 1] < 0x10000:
            events.append("%6d   pair in %s +%d: 0x%x" % (p, NAMES.get(op, "op%02x" % op), k, a))
    p += 1 + n
print("packets:", dict(cnt.most_common()))
for e in events: print(e)
