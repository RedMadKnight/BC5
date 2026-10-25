#!/usr/bin/env python3
# BC5 experiment 0288 (exp 0252's build0252.py with the unit changed): compile ~/bc5-work/exp0288/src/bc5LleAgc.0288.cpp
# (the shared tree's src/libs/bc5LleAgc.cpp plus patch0288.py's BC5_DIRECT_BREAKDOWN_AT, off by default) with the shared
# normal build's flags and link a separate kyty_emulator in ~/bc5-work/exp0288 from the shared build's other objects.
# The shared binary, its objects and ~/src/KytyPlus are not written.
# Run inside the ubuntu distrobox:  python3 -I build0288.py <compdb.json>   (ninja -t compdb -x of the shared build)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0288")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src", "bc5LleAgc.0288.cpp")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = None
for e in db:
    if e.get("output", "").endswith("/libs/bc5LleAgc.cpp.o"):
        UNIT = e["output"]
if UNIT is None:
    sys.exit("no bc5LleAgc.cpp.o unit in the compilation database")
units = {UNIT: os.path.join(OBJ, "bc5LleAgc.cpp.o")}


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=BUILD, check=True)


link = None
for e in db:
    out = e.get("output", "")
    if out == UNIT:
        argv = shlex.split(e["command"])
        clean, skip = [], 0
        for a in argv:
            if skip:
                skip -= 1
                continue
            if a in ("-MT", "-MF"):
                skip = 1
                continue
            if a == "-MD":
                continue
            clean.append(a)
        clean[clean.index("-o") + 1] = units[out]
        clean[clean.index("-c") + 1] = SRC
        run(clean)
    elif out == "src/kyty_emulator":
        link = e["command"]
if link is None:
    sys.exit("no link command")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]  # ninja wraps it in ": && ... && :"
for k, a in enumerate(argv):
    if a in units:
        argv[k] = units[a]
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert sum(a in units.values() for a in argv) == 1, "the object substituted"
run(argv)
