#!/usr/bin/env python3
# Experiment 0193: build window.cpp and controller.cpp from ~/src/KytyPlus and link a separate
# kyty_emulator in ~/bc5-work/exp0193 from the shared build's other objects. The shared binary
# (~/bc5-work/kytyplus-build/src/kyty_emulator) and its objects are not written.
# Run inside the ubuntu distrobox:  python3 build0193.py <compdb.json>
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0193")
OBJ = os.path.join(OUT, "obj")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
units = {
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/window/window.cpp.o": os.path.join(OBJ, "window.cpp.o"),
    "src/CMakeFiles/kyty_emulator.dir/libs/controller.cpp.o": os.path.join(OBJ, "controller.cpp.o"),
}


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(argv, cwd=BUILD, check=True)


link = None
for e in db:
    out = e.get("output", "")
    if out in units:
        argv = shlex.split(e["command"])
        clean = []
        skip = 0
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
        i = clean.index("-o")
        clean[i + 1] = units[out]
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
i = argv.index("-o")
argv[i + 1] = os.path.join(OUT, "kyty_emulator")
assert sum(a in units.values() for a in argv) == 2, "both objects substituted"
run(argv)
