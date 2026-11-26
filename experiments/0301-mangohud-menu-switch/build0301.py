#!/usr/bin/env python3
# BC5 (experiment 0301): compile the three units of the MangoHud switch (hostMenu.cpp, hostInput.cpp,
# settingsOverlay.cpp, with the changed hostMenu.h ahead of the tree's on the include path) with a shared build's
# flags and link a separate kyty_emulator in ~/bc5-work/exp0301/<flavour>/ from that build's other objects —
# exp 0273's build0273.py with a header and a choice of build. The shared builds, their objects and ~/src/KytyPlus
# are only read.
# Run inside the ubuntu distrobox:  python3 -I build0301.py <normal|lean> <compdb.json>   (run0301.sh build makes it)
import json, os, shlex, subprocess, sys

FLAVOUR = sys.argv[1]
BUILD = os.path.expanduser({"normal": "~/bc5-work/kytyplus-build", "lean": "~/bc5-work/kytyplus-build-lean"}[FLAVOUR])
E = os.path.expanduser("~/bc5-work/exp0301")
TREE = os.path.join(E, "tree", "src")  # the patched files, at their paths in the tree
OUT = os.path.join(E, FLAVOUR)
OBJ = os.path.join(OUT, "obj")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[2]))
UNITS = {
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/hostMenu.cpp.o": "graphics/presentation/hostMenu.cpp",
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/settingsOverlay.cpp.o": "graphics/presentation/settingsOverlay.cpp",
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/window/hostInput.cpp.o": "graphics/presentation/window/hostInput.cpp",
}


def obj_of(src):
    return os.path.join(OBJ, os.path.basename(src) + ".o")


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=BUILD, check=True)


link = None
compiled = 0
for e in db:
    out = e.get("output", "")
    if out in UNITS:
        src = UNITS[out]
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
        clean[clean.index("-o") + 1] = obj_of(src)
        clean[clean.index("-c") + 1] = os.path.join(TREE, src)
        clean.insert(1, "-I" + TREE)  # the changed hostMenu.h before the tree's own
        run(clean)
        compiled += 1
    elif out == "src/kyty_emulator":
        link = e["command"]
if compiled != len(UNITS):
    sys.exit(f"compiled {compiled} of {len(UNITS)} units: the compdb names them differently")
if link is None:
    sys.exit("no link command")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]  # ninja wraps it in ": && ... && :"
replaced = 0
for k, a in enumerate(argv):
    if a in UNITS:
        argv[k] = obj_of(UNITS[a])
        replaced += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert replaced == len(UNITS), f"{replaced} objects substituted, expected {len(UNITS)}"
run(argv)
