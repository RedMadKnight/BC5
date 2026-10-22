#!/usr/bin/env python3
# Experiment 0197 (from exp 0194): compile ~/bc5-work/exp0197/src/bc5LleAgc.cpp (a copy of ~/src/KytyPlus/src/libs/bc5LleAgc.cpp
# with edit0194.py and edit0197.py applied) with the shared build's own flags and link a separate kyty_emulator in
# ~/bc5-work/exp0197 from the shared build's other objects (exp 0193's build0193.py, one unit). The shared source,
# binary and objects are not written. Run inside the ubuntu distrobox:
#   (cd ~/bc5-work/kytyplus-build && ninja -t compdb -x > ~/bc5-work/exp0197/compdb.json)
#   python3 build0194.py ~/bc5-work/exp0197/compdb.json
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0197")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src", "bc5LleAgc.cpp")
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
obj = os.path.join(OBJ, "bc5LleAgc.cpp.o")


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(argv, cwd=BUILD, check=True)


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
        clean[clean.index("-o") + 1] = obj
        srcs = [k for k, a in enumerate(clean) if a.endswith("libs/bc5LleAgc.cpp")]
        assert len(srcs) == 1, srcs
        clean[srcs[0]] = SRC
        run(clean)
    elif out == "src/kyty_emulator":
        link = e["command"]
if link is None:
    sys.exit("no link command")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
for k, a in enumerate(argv):
    if a == UNIT:
        argv[k] = obj
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert sum(a == obj for a in argv) == 1, "object substituted"
run(argv)
