#!/usr/bin/env python3
# BC5 experiment 0251: build a private kyty_emulator as exp 0245 did (build0245.py): copy the shared tree's
# bc5LleAgc.cpp (the file the compile database names for libs/bc5LleAgc.cpp.o) and patch the copy three times:
#  1. edit0194.py (exp 0194, unchanged): BC5_DIRECT_DRAW_JOURNAL_EVERY, and every journalled indirect draw's arguments
#     at submission (SET_BASE index 1) and at the buffer's completion;
#  2. patch0245.py (exp 0245, unchanged): the "bake db" line with each journalled draw's depth/stencil state;
#  3. patch0251.py: the "bake db2" line with DB_HTILE_SURFACE and DB_RENDER_OVERRIDE2.
# Then compile it with the shared build's flags into ~/bc5-work/exp0251/obj and link ~/bc5-work/exp0251/kyty_emulator
# from the shared build's other objects. The shared tree (~/src/KytyPlus), the shared build's objects and its binary
# are not written.
# Run inside the ubuntu distrobox:  python3 -I build0251.py <compdb.json from "ninja -t compdb -x" in the shared build>
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0251")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src", "bc5LleAgc.0251.cpp")
os.makedirs(OBJ, exist_ok=True)
os.makedirs(os.path.dirname(SRC), exist_ok=True)
db = json.load(open(sys.argv[1]))
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
units = {UNIT: os.path.join(OBJ, "bc5LleAgc.cpp.o")}


def run(argv, cwd=BUILD):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=cwd, check=True)


link = None
for e in db:
    out = e.get("output", "")
    if out == UNIT:
        orig = e["file"] if os.path.isabs(e["file"]) else os.path.join(e["directory"], e["file"])
        s1, s2 = SRC + ".1", SRC + ".2"
        run(["python3", "-I", os.path.join(OUT, "edit0194.py"), orig, s1], cwd=OUT)
        run(["python3", "-I", os.path.join(OUT, "patch0245.py"), s1, s2], cwd=OUT)
        run(["python3", "-I", os.path.join(OUT, "patch0251.py"), s2, SRC], cwd=OUT)
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
print("built", os.path.join(OUT, "kyty_emulator"))
