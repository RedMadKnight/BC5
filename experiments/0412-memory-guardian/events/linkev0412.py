#!/usr/bin/env python3
"""BC5 exp 0412, build g412e (2026-11-11, the maintainer's "Tak, przenies"): the guardian's build g412d with the events cap.
exp 0411's link0411.py with two more private objects: src/kernel/eventQueue.cpp (exp 0401 e8's x5-eq source edited by
mkev0412.py) in place of e8's object, and src/graphics/host_gpu/renderer/sync.cpp (the shared source edited by
mkev0412.py), which no earlier build had as a private object. Every other private object is e8's (exp0401e8/obj)
except libAmpr.cpp.o and hostMenu.cpp.o, which are exp 0409's; the main unit is g412d's. The shared objects and archive
are only read.
usage (in the container): linkev0412.py <e8 dir> <exp0409 obj dir> <shared build dir> <out binary> <g412d unit> <obj dir>
                          <kit dir (event_cap0412.hpp)> <edited eventQueue.cpp> <edited sync.cpp>"""
import json
import os
import sys

e8, obj0409, build, out, unit, objdir, kit, eq_src, sy_src = sys.argv[1:10]
sys.path.insert(0, e8)
import build0401 as b  # noqa: E402  (e8's own copy)

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
inc = [os.path.join(e8, "mem", "src")]   # e8's own include list (link0411.py)
EQ, SY = "src/kernel/eventQueue.cpp", "src/graphics/host_gpu/renderer/sync.cpp"
assert b.unit_obj(EQ) in more, "e8 has no private eventQueue.cpp.o to replace"
assert b.unit_obj(SY) not in more, "sync.cpp is a private object already"
for rel, src in ((EQ, eq_src), (SY, sy_src)):
    o = os.path.join(objdir, os.path.basename(rel) + ".o")
    if b.run(b.compile_argv(db, src, o, [kit] + inc, b.unit_obj(rel)), build) != 0:
        print("== COMPILE FAILED", rel, flush=True)
        sys.exit(2)
    more[b.unit_obj(rel)] = o
main_obj = os.path.join(objdir, "bc5LleAgc.cpp.o")
if b.run(b.compile_argv(db, unit, main_obj, inc), build) != 0:
    print("== COMPILE FAILED", unit, flush=True)
    sys.exit(2)
print("private objects:", len(more) + 1, flush=True)
sys.exit(b.run(b.link_argv(db, main_obj, out, more, None), build))
