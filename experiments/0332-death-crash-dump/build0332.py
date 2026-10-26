#!/usr/bin/env python3
# BC5 (experiment 0332): compile ~/bc5-work/exp0332/src/runtimeLinker.0332.cpp (the shared tree's runtimeLinker.cpp,
# md5 f294dfc2, plus exp 0332's frame dump through patch0332.py) with the shared build's flags, and link a separate
# kyty_emulator in ~/bc5-work/exp0332. The link takes the shared normal build's other objects and exp 0330's compiled
# bc5LleAgc.cpp.o (~/bc5-work/exp0330/obj, the memory switches the test shortcut uses), as exp 0330's build0330.py
# links one substituted unit. The shared binary, its objects, exp 0330's files and ~/src/KytyPlus are not written.
# Run inside the ubuntu distrobox:  python3 -I build0332.py <compdb.json>   (run0332.sh build makes a fresh one)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0332")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src", "runtimeLinker.0332.cpp")
OBJ_0330 = os.path.expanduser("~/bc5-work/exp0330/obj/bc5LleAgc.cpp.o")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o"
UNIT_0330 = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
units = {UNIT: os.path.join(OBJ, "runtimeLinker.cpp.o"), UNIT_0330: OBJ_0330}
if not os.path.isfile(OBJ_0330):
    sys.exit(f"no {OBJ_0330} (exp 0330's run0330.sh build)")


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
assert sum(a in units.values() for a in argv) == 2, "both objects substituted"
run(argv)
