#!/usr/bin/env python3
# BC5 (experiment 0337): compile the three units patch0337.py wrote to ~/bc5-work/exp0337/src
# (graphics/presentation/window/hostInput.cpp, libs/libSystemService.cpp, graphics/presentation/settingsOverlay.cpp) with the
# shared build's flags and ~/bc5-work/exp0337/src first on the include path (the patched hostInput.h: declarations added
# only, so the units not rebuilt stay consistent), and link a separate kyty_emulator in ~/bc5-work/exp0337 from the shared
# normal build's other objects. The shared binary, its objects and ~/src/KytyPlus are not written.
# Run inside the ubuntu distrobox:  python3 -I build0337.py <compdb.json>   (run0337.sh build makes a fresh one)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0337")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
RELS = ["graphics/presentation/window/hostInput.cpp", "libs/libSystemService.cpp", "graphics/presentation/settingsOverlay.cpp"]
units = {f"src/CMakeFiles/kyty_emulator.dir/{r}.o": (os.path.join(OBJ, r.replace("/", "_") + ".o"), os.path.join(SRC, r)) for r in RELS}


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=BUILD, check=True)


link = None
done = set()
for e in db:
    out = e.get("output", "")
    if out in units:
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
        clean[clean.index("-o") + 1] = units[out][0]
        clean[clean.index("-c") + 1] = units[out][1]
        clean.insert(1, "-I" + SRC)  # the patched hostInput.h before the tree's
        run(clean)
        done.add(out)
    elif out == "src/kyty_emulator":
        link = e["command"]
if done != set(units):
    sys.exit(f"units not in the compdb: {sorted(set(units) - done)}")
if link is None:
    sys.exit("no link command")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]  # ninja wraps it in ": && ... && :"
objs = {k: v[0] for k, v in units.items()}
for k, a in enumerate(argv):
    if a in objs:
        argv[k] = objs[a]
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert sum(a in objs.values() for a in argv) == len(objs), "every object substituted"
run(argv)
