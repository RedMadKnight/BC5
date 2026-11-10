#!/usr/bin/env python3
"""BC5 exp 0401 series e11 (2026-11-10, the top session's relay of his "Tak"): exp 0409's binary with its main unit
replaced by e11's (e8's bc5LleAgc.cpp bd181169 + mkm110401.py, the six reset/learn switches). Every other private object
is e8's (exp0401e8/obj) except libAmpr.cpp.o and hostMenu.cpp.o, which are exp 0409's (exp0409/obj: the AMM scatter, unset
by default, and the install menu). The shared objects and archive are only read. With --gate, a CPU gate program is also
compiled with the main unit's command and linked with every emulator object but main.cpp.o (build0401.py's gate rule).
usage (in the container): link0411.py <e8 dir> <exp0409 obj dir> <shared build dir> <out binary> <e11 unit> <obj dir>
                          [--gate <source> <out>]"""
import json
import os
import sys

e8, obj0409, build, out, unit, objdir = sys.argv[1:7]
gate = sys.argv[7:]
assert gate in ([],) or (len(gate) == 3 and gate[0] == "--gate"), gate
sys.path.insert(0, e8)
import build0401 as b  # noqa: E402  (e8's own copy, the one e8 was linked with)

db = json.load(open(os.path.join(e8, "compdb.json"), encoding="utf-8"))
os.makedirs(objdir, exist_ok=True)
pre = "src/CMakeFiles/kyty_emulator.dir/"
more = {}
for f in sorted(os.listdir(os.path.join(e8, "obj"))):
    if not f.endswith(".cpp.o") or f == "bc5LleAgc.cpp.o":
        continue
    cands = [e["output"] for e in db if e.get("output", "").startswith(pre) and e["output"].endswith("/" + f)]
    assert len(cands) == 1, (f, cands)
    more[cands[0]] = os.path.join(e8, "obj", f)
for rel in ("src/libs/libAmpr.cpp", "src/graphics/presentation/hostMenu.cpp"):
    o = os.path.join(obj0409, os.path.basename(rel) + ".o")
    assert os.path.isfile(o), o
    more[b.unit_obj(rel)] = o
inc = [os.path.join(e8, "mem", "src")]   # e8's own include list for the main unit (box0401.sh: inc starts with $E/mem/src)
main_obj = os.path.join(objdir, "bc5LleAgc.cpp.o")
if b.run(b.compile_argv(db, unit, main_obj, inc), build) != 0:
    print("== COMPILE FAILED", unit, flush=True)
    sys.exit(2)
print("private objects:", len(more) + 1, flush=True)
link = b.link_argv(db, main_obj, out, more, None)
rc = b.run(link, build)
if rc == 0 and gate:
    gobj = os.path.join(objdir, "gate.o")
    if b.run(b.compile_argv(db, gate[1], gobj, inc), build) != 0:
        print("== COMPILE FAILED gate", gate[1], flush=True)
        sys.exit(2)
    rc = b.run(b.gate_argv(link, gobj, gate[2]), build)
sys.exit(rc)
