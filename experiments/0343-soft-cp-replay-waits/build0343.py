# BC5 experiment 0343: the shared normal build's compile command for src/libs/bc5LleAgc.cpp (ninja compdb) run on the
# PRIVATE patched copy into a private object, then the shared link command with that object and the shared backend
# archive swapped for the private ones (experiment 0346's ad7c2cb0). Nothing shared is written. Exp 0329's pattern.
import json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build, shared_archive, private_archive, out_bin = sys.argv[1:8]
UNIT = "src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o"
REL = "src/libs/bc5LleAgc.cpp"
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
comp = link = None
for e in json.load(open(db_path)):
    if e.get("output") == UNIT: comp = clean_compile(e["command"])
    if e.get("output") == "src/kyty_emulator": link = e["command"]
assert comp is not None and link is not None, "the unit or the link command is not in the compdb"
obj = os.path.join(out_dir, "obj", "bc5LleAgc.cpp.o")
os.makedirs(os.path.dirname(obj), exist_ok=True)
comp[comp.index("-o") + 1] = obj
comp[comp.index("-c") + 1] = os.path.join(src_root, REL)
comp.insert(1, "-I" + os.path.join(src_root, "src"))
if run(comp) != 0:
    print("== COMPILE FAILED", flush=True); sys.exit(2)
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = na = 0
for k, a in enumerate(argv):
    if a == UNIT: argv[k] = obj; nu += 1
    elif a == shared_archive: argv[k] = private_archive; na += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + out_bin + ".d"
assert nu == 1, f"the unit appears {nu} times in the link command"
assert na == 1, f"the shared archive appears {na} times in the link command"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv))
