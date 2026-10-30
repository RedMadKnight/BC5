#!/usr/bin/env python3
# BC5 experiment 0380 (after exp 0379's build0379t.py): the shared normal build's own link command for kyty_emulator
# (from `ninja -t compdb -x`), run in the shared build directory with only the backend archive swapped for
# a private one and the outputs (-o, the map, the dependency file) moved to a private path. Nothing shared is written;
# the objects are the shared build's as they are.
# usage: python3 link0380r.py <compdb.json> <shared build dir> <archive to link> <output binary>
import json
import shlex
import subprocess
import sys

db_path, build, archive, out_bin = sys.argv[1:5]
SHARED_ARCHIVE = "/bc5-work/backend-ubuntu/libbc5_backend.a"
db = json.load(open(db_path))
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
swapped = 0
for k, a in enumerate(argv):
    if a.endswith(SHARED_ARCHIVE):
        argv[k] = archive
        swapped += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out_bin + ".d"
assert swapped == 1, f"the shared archive appears {swapped} times in the link command"
argv[argv.index("-o") + 1] = out_bin
print("+", " ".join(argv)[:200], "...", flush=True)
sys.exit(subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode)
