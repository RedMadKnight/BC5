#!/usr/bin/env python3
# BC5 (experiment 0267; exp 0252's build0252.py with two units): compile the patched audio.cpp and controller.cpp
# (~/bc5-work/exp0267/src/libs/*.cpp = the shared tree's files plus rumble-thread-and-speaker-off.diff) with the
# shared normal build's flags into ~/bc5-work/exp0267/obj, and link a separate kyty_emulator in ~/bc5-work/exp0267
# from the shared build's other objects. The shared binary, its objects and ~/src/KytyPlus are only read.
# Run inside the ubuntu distrobox:  python3 -I build0267.py <compdb.json>   (ninja -t compdb -x of the shared build)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0267")
OBJ = os.path.join(OUT, "obj")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
units = {
    "src/CMakeFiles/kyty_emulator.dir/libs/audio.cpp.o": (os.path.join(OUT, "src", "libs", "audio.cpp"), os.path.join(OBJ, "audio.cpp.o")),
    "src/CMakeFiles/kyty_emulator.dir/libs/controller.cpp.o": (os.path.join(OUT, "src", "libs", "controller.cpp"), os.path.join(OBJ, "controller.cpp.o")),
}
for src, _ in units.values():
    if not os.path.isfile(src):
        sys.exit("missing patched source " + src)


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "10"] + argv, cwd=BUILD, check=True)


link = None
compiled = 0
for e in db:
    out = e.get("output", "")
    if out in units:
        src, obj = units[out]
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
        clean[clean.index("-o") + 1] = obj
        clean[clean.index("-c") + 1] = src
        run(clean)
        compiled += 1
    elif out == "src/kyty_emulator":
        link = e["command"]
if compiled != len(units):
    sys.exit("compiled %d of %d units (compile database changed?)" % (compiled, len(units)))
if link is None:
    sys.exit("no link command")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]  # ninja wraps it in ": && ... && :"
for k, a in enumerate(argv):
    if a in units:
        argv[k] = units[a][1]
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert sum(a in [u[1] for u in units.values()] for a in argv) == 2, "both objects substituted"
run(argv)
print("linked", os.path.join(OUT, "kyty_emulator"))
