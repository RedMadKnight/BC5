#!/usr/bin/env python3
# BC5 (experiment 0333): compile ~/bc5-work/exp0333/src/bc5LleAgc.0333.cpp (exp 0330's bc5LleAgc.mem.cpp, md5 29664e3c,
# plus exp 0333's zero map through patch0333.py) with the shared build's flags, and link a separate kyty_emulator in
# ~/bc5-work/exp0333. The link takes the shared normal build's other objects and exp 0332's compiled runtimeLinker.cpp.o
# (~/bc5-work/exp0332/obj, the extended crash dump), as exp 0332's build0332.py links two substituted units. The shared
# binary, its objects, exps 0330/0332's files and ~/src/KytyPlus are not written.
# Run inside the ubuntu distrobox:  python3 -I build0333.py <compdb.json>   (run0333.sh build makes a fresh one)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0333")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src", "bc5LleAgc.0333.cpp")
OBJ_0332 = os.path.expanduser("~/bc5-work/exp0332/obj/runtimeLinker.cpp.o")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
UNIT_0332 = "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o"
units = {UNIT: os.path.join(OBJ, "bc5LleAgc.cpp.o"), UNIT_0332: OBJ_0332}
if not os.path.isfile(OBJ_0332):
    sys.exit(f"no {OBJ_0332} (exp 0332's run0332.sh build)")


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
