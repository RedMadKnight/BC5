#!/usr/bin/env python3
# BC5 experiment 0380 (F611; build0380x.py for several units): compile the given units of kyty_emulator from private
# source files with the shared normal build's own compile commands (ninja compdb), into private objects, and run the
# shared link command with those objects swapped in (the shared backend archive as it is). Nothing shared is written.
# usage: python3 build0380y.py <compdb.json> <shared build dir> <private obj dir> <output binary> [--archive=<private libbc5_backend.a>] <unit>=<source>[=<quote dir>]...
#   --archive: link that backend archive in place of the shared one (the link command's libbc5_backend.a, exactly once)
#   <unit> as in the compdb without the prefix, e.g. libs/bc5LleAgc.cpp; <quote dir> goes in as -iquote (the unit's own
#   includes next to it in the tree)
import json
import os
import shlex
import subprocess
import sys

db_path, build, obj_dir, out_bin = sys.argv[1:5]
UNITS = []
ARCHIVE = None
for spec in sys.argv[5:]:
    if spec.startswith("--archive="):
        ARCHIVE = spec[len("--archive="):]
        continue
    parts = spec.split("=")
    UNITS.append(("src/CMakeFiles/kyty_emulator.dir/" + parts[0], parts[1], parts[2] if len(parts) > 2 else None))
assert UNITS, "no unit given"


def clean_compile(cmd):
    argv, out, skip = shlex.split(cmd), [], 0
    for a in argv:
        if skip:
            skip -= 1
            continue
        if a in ("-MT", "-MF"):
            skip = 1
            continue
        if a == "-MD":
            continue
        out.append(a)
    return out


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode


db = json.load(open(db_path))
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
os.makedirs(obj_dir, exist_ok=True)
objs = {}
for unit, src_file, quote_dir in UNITS:
    comp = next((clean_compile(e["command"]) for e in db if e.get("output") == unit), None)
    assert comp is not None, f"{unit} is not in the compdb"
    obj = os.path.join(obj_dir, os.path.basename(unit))
    comp[comp.index("-o") + 1] = obj
    comp[comp.index("-c") + 1] = src_file
    if quote_dir:
        comp.insert(1, "-iquote" + quote_dir)
    if run(comp) != 0:
        sys.exit("== COMPILE FAILED: " + unit)
    objs[unit] = obj
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
n = 0
for k, a in enumerate(argv):
    if a in objs:
        argv[k] = objs[a]
        n += 1
    elif ARCHIVE and a.endswith("/libbc5_backend.a"):
        argv[k] = ARCHIVE
        n_arch = n_arch + 1 if "n_arch" in dir() else 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out_bin + ".d"
assert n == len(objs), f"{n} of {len(objs)} units found in the link command"
assert not ARCHIVE or sum(1 for a in argv if a == ARCHIVE) == 1, "the archive is not in the link command exactly once"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv))
