#!/usr/bin/env python3
# BC5 (experiment 0221): compile ~/bc5-work/exp0221/src/bc5LleAgc.v3.cpp (the shared tree's bc5LleAgc.cpp plus
# patch0221b.py's v3 of the flip-timing diagnostic, BC5_DIRECT_FLIP_TRACE=1, off by default) with the shared build's flags and
# link ~/bc5-work/exp0221/kyty_emulator-v3 from the shared build's other objects (as exp 0219's
# build0219.py). The shared binary, its objects and ~/src/KytyPlus are not written.
# Run inside the ubuntu distrobox:  python3 -I build0221b.py <compdb.json>   (exp 0203's compdb.json of 10:43)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0221")
OBJ = os.path.join(OUT, "obj-v3")
SRC = os.path.join(OUT, "src", "bc5LleAgc.v3.cpp")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
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
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator-v3.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link-v3.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator-v3")
assert sum(a in units.values() for a in argv) == 1, "the object substituted"
run(argv)
