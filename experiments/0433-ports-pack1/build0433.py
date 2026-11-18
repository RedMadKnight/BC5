# BC5 experiment 0433 (exp 0429's build0429.py, generalised): the shared build's own compile commands for the private
# patched copies of the pack's units into private objects, then the shared link command with those objects swapped in.
# A unit is found in the compdb by its source path (not by a guessed object name). If its object is not on the link line
# itself but inside a static library that is, a private copy of that library gets the private member (`ar r`), and the
# link uses the copy. Used for the normal and the lean build (each with its own compdb and build directory), and for the
# backend archive (mode "archive"). Nothing shared is written.
#   emulator: build0433.py emu <compdb> <src_root> <out_dir> <build_dir> <out_bin> [ARCHIVE=<backend .a>] <unit> ...
#   backend:  build0433.py archive <compdb> <src_root> <out_dir> <build_dir> <shared .a> <out .a> <unit> ...
import json, os, shlex, shutil, subprocess, sys

mode = sys.argv[1]


def clean_compile(cmd):
    argv, clean, skip = shlex.split(cmd), [], 0
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
    return clean


def run(argv, cwd):
    print("+", " ".join(argv)[:240], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=cwd).returncode


def entry_for(db, build, rel):
    hits = [e for e in db if os.path.normpath(os.path.join(e.get("directory", build), e["file"])).endswith(os.sep + rel)]
    assert len(hits) == 1, f"{rel}: {len(hits)} compdb entries"
    return hits[0]


def compile_units(db, build, src_root, out_dir, units, include_root):
    objs = {}  # shared object path as written in the compdb output -> private object
    for rel in units:
        e = entry_for(db, build, rel)
        comp = e.get("arguments") or clean_compile(e["command"])
        comp = list(comp)
        out = e.get("output") or comp[comp.index("-o") + 1]
        obj = os.path.join(out_dir, "obj", rel.replace("/", "__") + ".o")
        os.makedirs(os.path.dirname(obj), exist_ok=True)
        comp[comp.index("-o") + 1] = obj
        comp[comp.index("-c") + 1] = os.path.join(src_root, rel)
        comp.insert(1, "-I" + os.path.join(src_root, include_root))
        if run(comp, e.get("directory", build)) != 0:
            print("== COMPILE FAILED:", rel, flush=True)
            sys.exit(2)
        objs[out] = obj
    return objs


def replace_members(lib_in, lib_out, members):
    """members: {member name in the archive: private object}. Copies the library and replaces each member once."""
    shutil.copyfile(lib_in, lib_out)
    names = subprocess.run(["ar", "t", lib_out], capture_output=True, text=True, check=True).stdout.split()
    for name, obj in members.items():
        assert names.count(name) == 1, f"{name} appears {names.count(name)} times in {lib_in}"
        tmp = os.path.join(os.path.dirname(lib_out), "member", name)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        shutil.copyfile(obj, tmp)
        assert subprocess.run(["ar", "r", lib_out, tmp]).returncode == 0, f"ar r {name}"


if mode == "archive":
    db_path, src_root, out_dir, build, shared_a, out_a = sys.argv[2:8]
    units = sys.argv[8:]
    db = json.load(open(db_path))
    objs = compile_units(db, build, src_root, out_dir, units, "include")
    replace_members(shared_a, out_a, {os.path.basename(k): v for k, v in objs.items()})
    sys.exit(0)

assert mode == "emu"
db_path, src_root, out_dir, build, out_bin = sys.argv[2:7]
ARCHIVE = None
units = []
for a in sys.argv[7:]:
    if a.startswith("ARCHIVE="):
        ARCHIVE = a[len("ARCHIVE="):]
        assert os.path.isfile(ARCHIVE), f"no archive {ARCHIVE}"
    else:
        units.append(a)
db = json.load(open(db_path))
link = next(e["command"] for e in db if e.get("output") == "src/kyty_emulator")
objs = compile_units(db, build, src_root, out_dir, units, "src")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
left = dict(objs)
for k, a in enumerate(argv):
    if a in left:
        argv[k] = left.pop(a)
# objects not on the link line: find the static library on the line that holds each of them
libs = {}
for out, obj in left.items():
    member = os.path.basename(out)
    owner = None
    for a in argv:
        if a.endswith(".a") and os.path.isfile(os.path.join(build, a)) and os.path.basename(a) != "libbc5_backend.a":
            names = subprocess.run(["ar", "t", os.path.join(build, a)], capture_output=True, text=True).stdout.split()
            if member in names:
                assert owner is None, f"{member} is in two libraries"
                owner = a
    assert owner is not None, f"{out} is neither on the link line nor in one of its libraries"
    libs.setdefault(owner, {})[member] = obj
for lib, members in libs.items():
    priv = os.path.join(out_dir, "lib", os.path.basename(lib))
    os.makedirs(os.path.dirname(priv), exist_ok=True)
    replace_members(os.path.join(build, lib), priv, members)
    argv = [priv if a == lib else a for a in argv]
    print(f"library {lib}: {len(members)} member(s) replaced in a private copy", flush=True)
for k, a in enumerate(argv):
    if a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + out_bin + ".d"
if ARCHIVE is not None:
    n = 0
    for k, a in enumerate(argv):
        if os.path.basename(a) == "libbc5_backend.a":
            argv[k] = ARCHIVE
            n += 1
    assert n >= 1, "no libbc5_backend.a in the link command"
argv[argv.index("-o") + 1] = out_bin
sys.exit(run(argv, build))
