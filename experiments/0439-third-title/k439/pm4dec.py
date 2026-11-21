# BC5 exp 0439 (problem 3): decode the PM4 packets of guest buffers read through /proc/<pid>/mem, listing every wait and
# every memory write with its address (packet forms: Mesa 0866ae7085c1 src/amd/common/sid.h opcodes; WAIT_REG_MEM
# 0x3c, RELEASE_MEM 0x49, EVENT_WRITE_EOP 0x47, WRITE_DATA 0x37, COPY_DATA 0x40, DMA_DATA 0x50, ATOMIC_MEM 0x1e,
# INDIRECT_BUFFER 0x3f, DISPATCH_DIRECT 0x15, DISPATCH_INDIRECT 0x16, SET_SH_REG 0x76). Private output only.
#   python3 -I pm4dec.py <pid> <addr:dwords> [<addr:dwords> ...] [watch=<lo>-<hi>]
import sys

pid = int(sys.argv[1])
bufs, watch = [], None
for a in sys.argv[2:]:
    if a.startswith("watch="):
        lo, hi = a[6:].split("-")
        watch = (int(lo, 16), int(hi, 16))
    else:
        x, n = a.split(":")
        bufs.append((int(x, 16), int(n)))
NAMES = {0x3c: "WAIT_REG_MEM", 0x49: "RELEASE_MEM", 0x47: "EVENT_WRITE_EOP", 0x37: "WRITE_DATA", 0x40: "COPY_DATA",
         0x50: "DMA_DATA", 0x1e: "ATOMIC_MEM", 0x3f: "INDIRECT_BUFFER", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT",
         0x46: "EVENT_WRITE", 0x10: "NOP", 0x76: "SET_SH_REG", 0x93: "WAIT_REG_MEM64", 0x58: "ACQUIRE_MEM", 0x22: "COND_EXEC"}
m = open(f"/proc/{pid}/mem", "rb")


def rd(a, n):
    m.seek(a)
    b = m.read(4 * n)
    return [int.from_bytes(b[4 * i:4 * i + 4], "little") for i in range(len(b) // 4)]


def a64(lo, hi):
    return (lo & ~3) | ((hi & 0xffff) << 32)


for base, n in bufs:
    w = rd(base, n)
    print(f"== buffer 0x{base:x}, {n} dwords")
    i, cnt, guard_end = 0, {}, 0
    while i < len(w):
        h = w[i]
        t = h >> 30
        c = (h >> 16) & 0x3fff
        ln = (c + 2) if t in (0, 3) and c != 0x3fff else 1
        if t == 3 and c != 0x3fff:
            op = (h >> 8) & 0xff
            cnt[op] = cnt.get(op, 0) + 1
            p = w[i:i + ln]
            name = NAMES.get(op, f"op 0x{op:02x}")
            addr = None
            note = ""
            if op in (0x3c, 0x93) and ln >= 7:
                addr = a64(p[2], p[3]); note = f"func {p[1] & 7} mem {(p[1] >> 4) & 1} ref 0x{p[4]:x} mask 0x{p[5]:x}"
            elif op == 0x49 and ln >= 7:
                addr = a64(p[3], p[4]); note = f"event 0x{p[1] & 0x3f:x} data_sel {(p[2] >> 29) & 7} INT_SEL {(p[2] >> 24) & 7} data 0x{p[6]:x}{p[5]:08x}" + (f" INT_CTXID 0x{p[7]:08x}" if ln >= 8 else "")
            elif op == 0x47 and ln >= 6:
                addr = a64(p[2], p[3]); note = f"event 0x{p[1] & 0x3f:x} data_sel {(p[3] >> 29) & 7} data 0x{p[5]:x}{p[4]:08x}"
            elif op == 0x37 and ln >= 4:
                addr = a64(p[2], p[3]); note = f"dst_sel {(p[1] >> 8) & 0xf} data " + " ".join(f"0x{x:x}" for x in p[4:8])
            elif op == 0x3f and ln >= 4:
                addr = a64(p[1], p[2]); note = f"size {p[3] & 0xfffff}"
            elif op == 0x1e and ln >= 5:
                addr = a64(p[2], p[3]); note = f"atomic 0x{p[1] & 0x7f:x} src 0x{p[5] if ln > 5 else 0:x}"
            elif op == 0x50 and ln >= 7:
                addr = a64(p[4], p[5]); note = f"dst; src 0x{a64(p[2], p[3]):x} bytes {p[6] & 0x1fffff}"
            if op == 0x22 and ln >= 5:
                g = a64(p[1], p[2]); cntv = p[4] & 0x3fff
                try:
                    gv = rd(g, 1)[0]
                except OSError:
                    gv = None
                note = f"guard 0x{g:x} = {('0x%08x' % gv) if gv is not None else 'unreadable'}, guards {cntv} dwords ({'SKIPPED' if gv == 0 else 'run'})"
                addr = None
            if guard_end > i:
                note += f"  [under COND_EXEC until @{guard_end}]"
            if op == 0x22 and ln >= 5:
                guard_end = i + ln + (p[4] & 0x3fff)
            show = op in (0x3c, 0x93, 0x49, 0x47, 0x37, 0x3f, 0x1e, 0x50, 0x40, 0x22) or (watch and addr and watch[0] <= addr < watch[1])
            if show:
                hit = "  <== WATCH" if watch and addr is not None and watch[0] <= addr < watch[1] else ""
                print(f"  @{i:5d} {name:16s} " + (f"addr 0x{addr:x} " if addr is not None else "") + note + hit)
        i += ln
    print("  counts: " + ", ".join(f"{NAMES.get(k, hex(k))} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
