#!/usr/bin/env python3
"""BC5 exp 0412, build g412f (2026-11-11): g412e with further private units, given as src/<rel>=<file> pairs.
exp 0411's link0411.py generalised: every private object is e8's (exp0401e8/obj) except libAmpr.cpp.o and hostMenu.cpp.o
(exp 0409's); each pair's unit is compiled with the shared build's command for that unit (e8's compdb.json), with the
include directories <inc dir>... then e8's mem/src, and replaces e8's object or is added. The main unit is compiled last.
The shared objects and archive are only read.
usage (in the container): linkmf0412.py <e8 dir> <exp0409 obj dir> <shared build dir> <out binary> <main unit> <obj dir>
                          <inc dir>[:<inc dir>...] src/<rel>=<file> [src/<rel>=<file> ...]"""
import json
import os
import sys

e8, obj0409, build, out, unit, objdir, incs = sys.argv[1:8]
pairs = [a.split("=", 1) for a in sys.argv[8:]]
assert pairs and all(len(p) == 2 and p[0].startswith("src/") and os.path.isfile(p[1]) for p in pairs), pairs
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
inc = [d for d in incs.split(":") if d] + [os.path.join(e8, "mem", "src")]
for rel, src in pairs:
    o = os.path.join(objdir, os.path.basename(rel) + ".o")
    print("private unit", rel, "(replaces e8's object)" if b.unit_obj(rel) in more else "(a new private object)", flush=True)
    if b.run(b.compile_argv(db, src, o, inc, b.unit_obj(rel)), build) != 0:
        print("== COMPILE FAILED", rel, flush=True)
        sys.exit(2)
    more[b.unit_obj(rel)] = o
main_obj = os.path.join(objdir, "bc5LleAgc.cpp.o")
# BC5_0412_MAIN_EXTRA (build g412i): further compiler words for the main unit, e.g. -g1 for line tables (no change of the code).
main_extra = os.environ.get("BC5_0412_MAIN_EXTRA", "").split()
if main_extra:
    print("main unit extra words:", main_extra, flush=True)
if b.run(b.compile_argv(db, unit, main_obj, [os.path.join(e8, "mem", "src")]) + main_extra, build) != 0:
    print("== COMPILE FAILED", unit, flush=True)
    sys.exit(2)
print("private objects:", len(more) + 1, flush=True)
sys.exit(b.run(b.link_argv(db, main_obj, out, more, None), build))
