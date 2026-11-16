# BC5 experiment 0429 (exp 0425's build0425.py, exp 0388's pattern): the shared build's compile commands for the private
# patched copies of six units into private objects, then the shared link command with those objects swapped in.
# Used for both the normal and the lean build (each with its own compdb and build directory). Nothing shared is written.
import json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build, out_bin = sys.argv[1:6]
EXTRA = sys.argv[6:]  # none in exp 0429
UNITS = {
    "src/CMakeFiles/kyty_emulator.dir/kernel/pthread.cpp.o": "src/kernel/pthread.cpp",
    "src/CMakeFiles/kyty_emulator.dir/kernel/semaphore.cpp.o": "src/kernel/semaphore.cpp",
    "src/CMakeFiles/kyty_emulator.dir/loader/gamePatch.cpp.o": "src/loader/gamePatch.cpp",
    "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o": "src/loader/runtimeLinker.cpp",
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/hostMenu.cpp.o": "src/graphics/presentation/hostMenu.cpp",
    "src/CMakeFiles/kyty_emulator.dir/graphics/presentation/window/hostInput.cpp.o": "src/graphics/presentation/window/hostInput.cpp",
}
PREBUILT = {}  # exp 0429: "<unit .o>=<object path>": link this object in place of the shared one, no compile
for rel in EXTRA:
    if "=" in rel:
        unit, path = rel.split("=", 1)
        assert os.path.isfile(path), f"no prebuilt object {path}"
        PREBUILT[unit] = path
        continue
    UNITS["src/CMakeFiles/kyty_emulator.dir/" + rel[len("src/"):] + ".o"] = rel
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
objs.update(PREBUILT)
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
seen = {u: 0 for u in list(UNITS) + list(PREBUILT)}
for k, a in enumerate(argv):
    if a in objs: argv[k] = objs[a]; seen[a] += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + out_bin + ".d"
for u, n in seen.items():
    assert n == 1, f"{u} appears {n} times in the link command"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv))
