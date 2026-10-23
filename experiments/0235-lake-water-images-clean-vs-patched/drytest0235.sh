#!/usr/bin/env bash
# exp 0235 dry test: a helper process maps anonymous memory at the water images' kinds of addresses (no title data),
# a fake journal names them, img0235.py dump reads them, img0235.py sum summarises two synthetic shots.
set -u
T=~/bc5-work/exp0235/test; rm -rf $T; mkdir -p $T/run/dumps; cd $T
cat > helper.py <<'PY'
import ctypes, os, random, struct, sys, time
libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
for base, size in ((0x113cb40000, 16 << 20), (0x1200000000, 4 << 20), (0x1210000000, 1 << 20), (0x1220000000, 4096)):
    p = libc.mmap(base, size, 3, 0x22 | 0x100000, -1, 0)  # PROT_READ|WRITE, MAP_PRIVATE|ANON|FIXED_NOREPLACE
    assert p == base, (hex(base), p, ctypes.get_errno())
    ctypes.memmove(base, bytes(random.getrandbits(8) for _ in range(min(size, 65536))), min(size, 65536))
open(sys.argv[1], "w").write("ready\n")
time.sleep(60)
PY
python3 -I helper.py $T/ready & HP=$!
for _ in $(seq 1 20); do [ -f $T/ready ] && break; sleep 0.5; done
python3 -I - > journal.log <<'PY'
def t(base, w, h, fmt, levels, sw):
    d0 = (base >> 8) & 0xffffffff
    d1 = ((base >> 40) & 0xff) | fmt << 20 | ((w - 1) & 3) << 30
    d2 = (((w - 1) >> 2) & 0xfff) | ((h - 1) & 0x3fff) << 14
    d3 = (levels - 1) << 16 | sw << 20 | 9 << 28
    return [d0, d1, d2, d3, 0, 0, 0, 0]
ps = t(0x1200000000, 2048, 2048, 175, 8, 5) + t(0x1210000000, 512, 512, 13, 7, 5) + t(0x1220000000, 4, 4, 56, 1, 5) + [0] * 8
gs = [0] * 16 + t(0x113cb40000, 2560, 1440, 13, 1, 27) + [0] * 8
print("timing: t 151.0 s")
print("draw journal buf 3 (12156 dwords) at 2105: c0042700 | rt0 113f230000 2560x1440 info 0 mask 0 | vp 2560x-1440 at 0,1440 | ps 11d01ff900 es 11d0148800 gs 0000000000 cs 11d0288a00")
print("bake ud ps buf 3 at 2105: " + " ".join("%08x" % x for x in ps))
print("bake ud gs buf 3 at 2105: " + " ".join("%08x" % x for x in gs))
PY
python3 -I ~/bc5-work/exp0235/img0235.py dump $HP $T/journal.log $T/run/dumps/ts00.img 5
python3 -I ~/bc5-work/exp0235/img0235.py dump $HP $T/journal.log $T/run/dumps/ts01.img 5
cat run/dumps/ts00.img.desc.txt; ls -la run/dumps
kill $HP
printf "  140000-ts00.png: patch  25.0 %%\n  140005-ts01.png: patch   1.0 %%\n" > bench.txt
time python3 -I ~/bc5-work/exp0235/img0235.py sum $T/run $T/bench.txt
python3 -I ~/bc5-work/exp0235/img0235.py dump 1 $T/none.log $T/run/dumps/ts02.img 2
