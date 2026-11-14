#!/usr/bin/env bash
# BC5 exp 0419: the second read-only pass over the title's code (audio-record-fault.md section 8). It uses the
# disassembly eread0419.sh left on the box and the title's data segment to answer: which functions call the "fill"
# candidates and the buffer-release function, and in which function tables (by table offset) they sit.
# Same conditions as eread0419.sh: no emulator, BOX-LOCK empty, ONE lock line for the whole pass, nice 19, output
# stays under ~/bc5-work/exp0419/eread; what is printed is addresses and counts.
# usage (on the box): nice -n 19 bash eread0419b.sh <eboot.bin> <hex address>...
set -u
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; O=$W/exp0419/eread
pgrep '^kyty_emulator' > /dev/null && { echo "eread0419b: an emulator is running: NOT STARTED"; exit 1; }
[ -s "$W/BOX-LOCK" ] && { echo "eread0419b: BOX-LOCK is not empty: NOT STARTED"; cat "$W/BOX-LOCK"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0419: second read-only pass over the title's code and tables (no emulator, nice 19, CPU only; about 10 minutes)" 15 || { echo "eread0419b: NOT STARTED"; exit 1; }
trap chain_release EXIT
[ -s "$O/dis.txt" ] || { echo "eread0419b: no disassembly"; exit 1; }
EB=$1; shift
python3 - "$EB" "$O/dis.txt" "$@" << 'PYEOF'
import re, struct, sys
eb, dis = sys.argv[1:3]
targets = [int(x, 16) for x in sys.argv[3:]]
b = open(eb, "rb").read()
n, = struct.unpack_from("<H", b, 0x18)
seg = {}
for i in range(n):
    props, off, fsz, msz = struct.unpack_from("<QQQQ", b, 0x20 + 0x20 * i)
    if props & 0x800:
        seg[(props >> 20) & 0xfff] = off
eh = 0x20 + 0x20 * n
phoff, = struct.unpack_from("<Q", b, eh + 0x20)
phentsize, phnum = struct.unpack_from("<HH", b, eh + 0x36)
data = []  # (vaddr, bytes) of the loadable segments that are not code
for i in range(phnum):
    t, fl, off, va, pa, fsz, msz, al = struct.unpack_from("<IIQQQQQQ", b, eh + phoff + i * phentsize)
    if t == 1 and not (fl & 1) and i in seg and fsz:
        data.append((va, b[seg[i]:seg[i] + fsz]))
# the disassembly: address -> (line number, text); function starts = an instruction after int3 padding or a ret
addr_re = re.compile(r"^\s*([0-9a-f]+):\t[0-9a-f ]+\t(.*)$")
ins = []
for line in open(dis, errors="replace"):
    m = addr_re.match(line)
    if m:
        ins.append((int(m.group(1), 16), m.group(2).strip()))
starts = []
prev = "int3"
for a, t in ins:
    if (prev.startswith("int3") or prev.startswith("ret") or prev.startswith("jmp")) and not t.startswith("int3") and (a & 0xf) == 0:
        starts.append(a)
    prev = t
import bisect
def func(a):
    i = bisect.bisect_right(starts, a) - 1
    return starts[i] if i >= 0 else 0
# The image is position independent: a function table in the data segment is zero in the file and is filled by
# relative relocations (offset, info with type 8, addend). slot address -> function address, from every such triple.
rel = {}
for va, d in data:
    for p in range(16, len(d) - 7, 8):
        info, add = struct.unpack_from("<QQ", d, p - 8)
        if (info & 0xffffffff) == 8 and 0x1000 <= add < 0x5f22000:
            rel[struct.unpack_from("<Q", d, p - 16)[0]] = add
print("relative relocations to code: %d" % len(rel))
by_fn = {}
for slot, add in rel.items():
    by_fn.setdefault(add, []).append(slot)
def rtables(f):
    out = []
    for slot in sorted(by_fn.get(f, [])):
        s = slot
        while (s - 8) in rel:
            s -= 8
        row = []
        x = s
        while x in rel and len(row) < 14:
            row.append("%x" % rel[x])
            x += 8
        out.append("table %#x slot +%#x: %s" % (s, slot - s, " ".join(row)))
    return out
def tables(f):
    for line in rtables(f)[:6]:
        print("      " + line)
    out = []
    key = struct.pack("<Q", f)
    for va, d in data:
        p = d.find(key)
        while p >= 0:
            if p % 8 == 0:
                # walk back to the table's start: the first slot after a non-code value
                q = p
                while q >= 8:
                    v, = struct.unpack_from("<Q", d, q - 8)
                    if not (0x1000 <= v < 0x5f22000):
                        break
                    q -= 8
                out.append((va + q, p - q))
            p = d.find(key, p + 1)
    return out
def report(t, depth=0):
    f = func(t)
    callers = sorted({func(a) for a, x in ins if re.match(r"(call|jmp)\s+0x%x$" % t, x)})
    tb = tables(t)
    print("%s%#x: %d direct callers %s; in tables: %s" % ("  " * depth, t, len(callers), " ".join("%#x" % c for c in callers[:12]),
          " ".join("%#x+%#x" % x for x in tb[:8]) or "none"))
    return callers
for t in targets:
    print("== target %#x (function start %#x)" % (t, func(t)))
    seen = set()
    level = [t]
    for depth in range(3):
        nxt = []
        for x in level:
            if x in seen:
                continue
            seen.add(x)
            nxt += report(x, depth)
        level = nxt[:12]
PYEOF
echo "eread0419b ended $(date +%T)"
