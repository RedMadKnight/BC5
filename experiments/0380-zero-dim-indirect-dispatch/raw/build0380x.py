#!/usr/bin/env python3
# BC5 experiment 0380 (F595; build0380m.py with the unit as an argument): compile ONE unit, src/libs/bc5LleAgc.cpp, from a given
# source file with the shared normal build's own compile command (ninja compdb), into a private object, and run the
# shared link command with that object swapped in (the shared backend archive as it is). Nothing shared is written.
# usage: python3 build0380x.py <compdb.json> <shared build dir> <bc5LleAgc.cpp to compile> <private obj dir> <output binary> [tree src/libs dir]
# (the last argument goes in as -iquote, for the unit's own includes next to it)
import json
import os
import shlex
import subprocess
import sys

db_path, build, src_file, obj_dir, out_bin = sys.argv[1:6]
quote_dir = sys.argv[6] if len(sys.argv) > 6 else None
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"


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
comp = next((clean_compile(e["command"]) for e in db if e.get("output") == UNIT), None)
assert comp is not None, f"{UNIT} is not in the compdb"
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
os.makedirs(obj_dir, exist_ok=True)
obj = os.path.join(obj_dir, "bc5LleAgc.cpp.o")
comp[comp.index("-o") + 1] = obj
comp[comp.index("-c") + 1] = src_file
if quote_dir:
    comp.insert(1, "-iquote" + quote_dir)
if run(comp) != 0:
    sys.exit("== COMPILE FAILED")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
n = 0
for k, a in enumerate(argv):
    if a == UNIT:
        argv[k] = obj
        n += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out_bin + ".d"
assert n == 1, f"{UNIT} appears {n} times in the link command"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv))
