#!/usr/bin/env python3
# BC5 (experiment 0276): compile the two patched units (audio.cpp, libAmpr.cpp) with the shared build's flags and
# link a separate kyty_emulator in ~/bc5-work/exp0276 from the shared normal build's other objects — exp 0273's
# build0273.py for two units. The shared binary, its objects and ~/src/KytyPlus are only read.
# Run inside the ubuntu distrobox:  python3 -I build0276.py <compdb.json>   (run0276.sh build makes a fresh one)
import json, os, shlex, subprocess, sys

BUILD = os.path.expanduser("~/bc5-work/kytyplus-build")
OUT = os.path.expanduser("~/bc5-work/exp0276")
OBJ = os.path.join(OUT, "obj")
SRC = os.path.join(OUT, "src")
os.makedirs(OBJ, exist_ok=True)
db = json.load(open(sys.argv[1]))
UNITS = {
    "src/CMakeFiles/kyty_emulator.dir/libs/audio.cpp.o": ("audio.cpp", os.path.join(OBJ, "audio.cpp.o")),
    "src/CMakeFiles/kyty_emulator.dir/libs/libAmpr.cpp.o": ("libAmpr.cpp", os.path.join(OBJ, "libAmpr.cpp.o")),
}


def run(argv):
    print("+", " ".join(argv)[:200], "...", flush=True)
    subprocess.run(["nice", "-n", "19"] + argv, cwd=BUILD, check=True)


link = None
compiled = 0
for e in db:
    out = e.get("output", "")
    if out in UNITS:
        src_name, obj = UNITS[out]
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
        clean[clean.index("-c") + 1] = os.path.join(SRC, src_name)
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
        argv[k] = UNITS[a][1]
        replaced += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(OUT, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(OUT, "link.d")
argv[argv.index("-o") + 1] = os.path.join(OUT, "kyty_emulator")
assert replaced == len(UNITS), f"{replaced} objects substituted, expected {len(UNITS)}"
run(argv)
