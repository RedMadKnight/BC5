#!/usr/bin/env python3
# BC5 experiment 0291: compile ~/bc5-work/exp0291/src/videoOut.cpp (the shared tree's file plus patch_0291, made by
# apply0291.py) with the normal shared build's flags and link a separate emulator,
# ~/bc5-work/exp0291/bin/kyty_emulator (the file name kept, so its process name is kyty_emulator), from the shared
# build's other objects, as exp 0203's build0203.py did. The shared binary, its objects and ~/src/KytyPlus are not
# written. Run inside the ubuntu distrobox:  python3 -I build0291.py <compdb.json>  (ninja -t compdb of the build)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0291")
OBJ = os.path.join(OUT, "obj")
BIN = os.path.join(OUT, "bin")
SRC = os.path.join(OUT, "src", "videoOut.cpp")
os.makedirs(OBJ, exist_ok=True)
os.makedirs(BIN, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/videoOut.cpp.o"
units = {UNIT: os.path.join(OBJ, "videoOut.cpp.o")}


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=BUILD, check=True)


link = None
compiled = False
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
        compiled = True
    elif out == "src/kyty_emulator":
        link = e["command"]
if not compiled:
    sys.exit("no compile command for " + UNIT)
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
argv[argv.index("-o") + 1] = os.path.join(BIN, "kyty_emulator")
assert sum(a in units.values() for a in argv) == 1, "the object substituted"
run(argv)
