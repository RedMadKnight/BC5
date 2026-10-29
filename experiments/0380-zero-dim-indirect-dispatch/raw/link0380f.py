#!/usr/bin/env python3
# BC5 experiment 0380, test shortcut "0380 fix + 0379" (link0380r.py + exp 0379's build0379t.py): the shared normal build's
# own link command for kyty_emulator (from `ninja -t compdb -x`), run in the shared build directory with two inputs
# swapped: src/libs/bc5LleAgc.cpp's object for exp 0379t's private one (the zero skip, compiled by build0379t.sh) and
# the backend archive for a private one. The outputs (-o, the map, the dependency file) go to a private path. Nothing
# shared is written and nothing is compiled.
# usage: python3 link0380f.py <compdb.json> <shared build dir> <bc5LleAgc.cpp.o> <archive> <output binary>
import json
import shlex
import subprocess
import sys

db_path, build, unit_obj, archive, out_bin = sys.argv[1:6]
SHARED_ARCHIVE = "/bc5-work/backend-ubuntu/libbc5_backend.a"
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
db = json.load(open(db_path))
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
swapped_archive = swapped_unit = 0
for k, a in enumerate(argv):
    if a.endswith(SHARED_ARCHIVE):
        argv[k] = archive
        swapped_archive += 1
    elif a == UNIT:
        argv[k] = unit_obj
        swapped_unit += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out_bin + ".d"
assert swapped_archive == 1, f"the shared archive appears {swapped_archive} times in the link command"
assert swapped_unit == 1, f"{UNIT} appears {swapped_unit} times in the link command"
argv[argv.index("-o") + 1] = out_bin
print("+", " ".join(argv)[:200], "...", flush=True)
sys.exit(subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode)
