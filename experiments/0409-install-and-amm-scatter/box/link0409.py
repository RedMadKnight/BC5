#!/usr/bin/env python3
"""BC5 exp 0409 (top session, 2026-11-09): e8's binary with two more private units: libAmpr.cpp (e8's amm unit plus
the AMM scatter edit, KYTY_BC5_AMM_SCATTER) and graphics/presentation/hostMenu.cpp (File > Install game...).
Every other private object is e8's (already compiled in its obj dir); the shared objects and archive are only read.
usage (in the container): link0409.py <e8 dir> <obj dir> <shared build dir> <out binary> <libAmpr.cpp> <hostMenu.cpp>"""
import json, os, sys
e8, objdir, build, out, ampr, menu = sys.argv[1:7]
sys.path.insert(0, e8)
import build0401 as b
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
inc = [os.path.join(e8, "mem", "src")]
for rel, path in (("src/libs/libAmpr.cpp", ampr), ("src/graphics/presentation/hostMenu.cpp", menu)):
    o = os.path.join(objdir, os.path.basename(rel) + ".o")
    if b.run(b.compile_argv(db, path, o, inc, b.unit_obj(rel)), build) != 0:
        print("== COMPILE FAILED", rel, flush=True)
        sys.exit(2)
    more[b.unit_obj(rel)] = o
print("private objects:", len(more), flush=True)
link = b.link_argv(db, os.path.join(e8, "obj", "bc5LleAgc.cpp.o"), out, more, None)
sys.exit(b.run(link, build))
