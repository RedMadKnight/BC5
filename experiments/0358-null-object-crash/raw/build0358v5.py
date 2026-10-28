# BC5 experiment 0358 (exp 0343's build0343.py for three units (trap v2)): the shared normal build's compile commands
# (ninja compdb) for the PRIVATE patched copies of src/kernel/pthread.cpp, src/libs/bc5LleAgc.cpp and
# src/loader/runtimeLinker.cpp into private objects, then the shared link command with those objects swapped
# in (the shared backend archive as it is). Nothing shared is written.
import json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build, out_bin = sys.argv[1:6]
UNITS = {
    
    "src/CMakeFiles/kyty_emulator.dir/kernel/pthread.cpp.o": "src/kernel/pthread.cpp",
    "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o": "src/loader/runtimeLinker.cpp",
    "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o": "src/libs/bc5LleAgc.cpp",
    "src/CMakeFiles/kyty_emulator.dir/kernel/semaphore.cpp.o": "src/kernel/semaphore.cpp",
}
def clean_compile(cmd):
    argv, clean, skip = shlex.split(cmd), [], 0
    for a in argv:
        if skip: skip -= 1; continue
        if a in ("-MT", "-MF"): skip = 1; continue
        if a == "-MD": continue
        clean.append(a)
    return clean
def run(argv):
    print("+", " ".join(argv)[:240], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode
db = json.load(open(db_path))
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
objs = {}
for unit, rel in UNITS.items():
    comp = next((clean_compile(e["command"]) for e in db if e.get("output") == unit), None)
    assert comp is not None, f"{unit} is not in the compdb"
    obj = os.path.join(out_dir, "obj", os.path.basename(unit))
    os.makedirs(os.path.dirname(obj), exist_ok=True)
    comp[comp.index("-o") + 1] = obj
    comp[comp.index("-c") + 1] = os.path.join(src_root, rel)
    comp.insert(1, "-I" + os.path.join(src_root, "src"))
    if run(comp) != 0:
        print("== COMPILE FAILED:", rel, flush=True); sys.exit(2)
    objs[unit] = obj
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
seen = {u: 0 for u in UNITS}
for k, a in enumerate(argv):
    if a in objs: argv[k] = objs[a]; seen[a] += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + out_bin + ".d"
for u, n in seen.items():
    assert n == 1, f"{u} appears {n} times in the link command"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv))
