# PORT-NP / PORT-LIBC, the box's CPU check: run inside the ubuntu distrobox by boxcheck_port.sh, as exp 0328's build0328.py
# did. Compiles the two fixed units from the patched tree with the shared build's own flags, relinks a private
# kyty_emulator (never run), then builds and runs three test programs. Nothing shared is written.
# usage: boxbuild_port.py <compdb.json> <patched tree> <out dir> <shared build> <test dir>
import json
import os
import shlex
import subprocess
import sys

db_path, tree, out_dir, build, test_dir = sys.argv[1:6]
UNITS = {
    "src/libs/libC.cpp": "src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o",
    "src/libs/libNpCppWebApi.cpp": "src/CMakeFiles/kyty_emulator.dir/libs/libNpCppWebApi.cpp.o",
}
NP_OBJ = UNITS["src/libs/libNpCppWebApi.cpp"]
obj_dir = os.path.join(out_dir, "obj")
os.makedirs(obj_dir, exist_ok=True)


def run(argv, check=True, env=None):
    print("+", " ".join(argv)[:220], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=check, env=env)


def clean_compile(cmd):
    clean, skip = [], 0
    for a in shlex.split(cmd):
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


objs, link, flags = {}, None, None
for e in json.load(open(db_path)):
    out = e.get("output", "")
    for rel, unit in UNITS.items():
        if out == unit:
            obj = os.path.join(obj_dir, os.path.basename(rel) + ".o")
            clean = clean_compile(e["command"])
            clean[clean.index("-o") + 1] = obj
            clean[clean.index("-c") + 1] = os.path.join(tree, rel)
            clean.insert(1, "-I" + os.path.join(tree, "src"))
            run(clean)
            objs[unit] = obj
            flags = clean
    if out == "src/kyty_emulator":
        link = e["command"]
assert len(objs) == len(UNITS), f"compiled {len(objs)} of {len(UNITS)} units"
assert link is not None

argv = [a for a in shlex.split(link) if a not in (":", "&&")]
replaced = 0
for k, a in enumerate(argv):
    if a in objs:
        argv[k] = objs[a]
        replaced += 1
    elif a.startswith("-Wl,-Map="):
        argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="):
        argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert replaced == len(UNITS), f"units replaced {replaced} times"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
run(argv)
print("== emulator linked (not run)", flush=True)

cxx = argv[0]
libs = [a for a in argv if a.startswith("-l") or a.startswith("-L") or a.endswith(".a") or a.endswith(".so")
        or a.startswith("-Wl,-rpath") or a.startswith("-pthread")]
all_objs = [a for a in argv if a.endswith(".o") and not a.endswith("/main.cpp.o")]
np_private = objs[NP_OBJ]


def compile_test(src, extra=()):
    obj = os.path.join(obj_dir, os.path.basename(src) + "".join(e.strip("-=") for e in extra) + ".o")
    tc = list(flags) + list(extra)
    tc[tc.index("-o") + 1] = obj
    tc[tc.index("-c") + 1] = src
    run(tc)
    return obj


def link_test(name, obj, objects, extra=()):
    binary = os.path.join(out_dir, name)
    r = run([cxx, *extra, "-o", binary, obj] + objects + libs + ["-lpthread"], check=False)
    return binary if r.returncode == 0 else None


rc = 0

# 1. exp 0328's tests, untouched, against the fixed unit
binary = link_test("np_cpp_web_api_tests", compile_test(os.path.join(test_dir, "NpCppWebApiTests.cpp")), all_objs)
r = run([binary], check=False) if binary else None
print("== np_cpp_web_api_tests exit", r.returncode if r else "NO LINK", flush=True)
rc = rc or (0 if r and r.returncode == 0 else 1)

# 2. the libc registrations through InitAll on the real SymbolDatabase
binary = link_test("libc_nid_tests", compile_test(os.path.join(test_dir, "LibcNidTests.cpp")), all_objs)
r = run([binary], check=False) if binary else None
print("== libc_nid_tests exit", r.returncode if r else "NO LINK", flush=True)
rc = rc or (0 if r and r.returncode == 0 else 2)

# 3. the aliasing tests: the unit is inside the test, so its object stays out of the link. ASan where it links.
others = [o for o in all_objs if o != np_private]
src = os.path.join(test_dir, "NpAliasTests.cpp")
asan = ("-fsanitize=address", "-fno-omit-frame-pointer")
binary = link_test("np_alias_tests_asan", compile_test(src, asan), others, asan)
sanitized = binary is not None
if binary is None:
    print("== ASan link failed: the same tests with the tracker alone", flush=True)
    binary = link_test("np_alias_tests", compile_test(src), others)
if binary is None:
    print("== np_alias_tests NO LINK", flush=True)
    sys.exit(rc or 3)
env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:detect_odr_violation=0")  # the tracker counts leaks
cases = subprocess.run([binary, "list"], env=env, stdout=subprocess.PIPE, text=True, check=True).stdout.split()
failed = 0
for case in cases:
    r = run([binary, case], check=False, env=env)
    print("==", case, "exit", r.returncode, flush=True)
    failed += r.returncode != 0
print(f"== np_alias_tests {'ASan' if sanitized else 'no ASan'}: {len(cases) - failed}/{len(cases)} cases pass", flush=True)
sys.exit(rc or (4 if failed else 0))
