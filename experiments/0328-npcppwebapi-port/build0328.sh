#!/usr/bin/env bash
# BC5 experiment 0328: one private emulator, ~/bc5-work/exp0328/kyty_emulator, carrying exp 0327's twelve imports AND the
# port of AnyPS5's libSceNpCppWebApi, from the shared normal build's objects: patch0328.py (0327's seven files + the
# libs.cpp registration) applied to the tree ~/src/KytyPlus (f266548 + patch 0001), the new unit libNpCppWebApi.cpp
# copied in beside them, SEVEN units compiled with the shared flags (the patched headers first), relinked against the
# shared objects and the shared archive (825ae1d1); then the two test programs (the sync-on-address tests of 0327, the
# NpCppWebApi tests of 0328) built against the patched units and run — a failing test ends the script after the
# emulator was linked. A previous kyty_emulator is kept under its md5. Nothing shared is written; ~/src/KytyPlus is read.
# usage: build0328.sh   (on the box; CPU only, nice 19, under the BOX-LOCK; no emulator runs; ~2 min)
set -u
E=$HOME/bc5-work/exp0328; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-825ae1d1}; EXPECT_NORMAL=${EXPECT_NORMAL:-5dd77a82}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$R" "$E/src" "$E/obj"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 5bccbb80 ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80 (the tree changed): stop"; exit 1; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop (EXPECT_ARCHIVE=... to accept)"; exit 1; }
for f in patch0328.py libNpCppWebApi.cpp SyncOnAddressTests.cpp NpCppWebApiTests.cpp; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
echo "bvh exp 0328 | build of ~/bc5-work/exp0328/kyty_emulator (seven units compiled + relink against the shared objects; two test programs; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0328 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "tree $(cd "$K" && git log -1 --format=%h 2>/dev/null) bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp")"
  for f in src/kernel/syncOnAddress.h src/kernel/syncOnAddress.cpp src/libs/libKernel.cpp src/kernel/fileSystem.h src/kernel/fileSystem.cpp src/libs/libC.cpp src/loader/runtimeLinker.cpp src/libs/libs.cpp; do echo "  $f $(m "$K/$f")"; done
  echo "  libNpCppWebApi.cpp (new) $(m "$HERE/libNpCppWebApi.cpp")"
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH")"; } > "$R/build-inputs.txt"
echo "== $(date +%T) patch"
[ "$HERE/patch0328.py" -ef "$E/patch0328.py" ] || cp "$HERE/patch0328.py" "$E/patch0328.py"
distrobox enter ubuntu -- python3 -I "$E/patch0328.py" "$K" "$E/src" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "patch0328.py failed"; exit 1; }
cat "$R/patch.out"
cp "$E/src/patch_0328.diff" "$R/patch_0328.diff"
mkdir -p "$E/src/src/libs" && cp "$HERE/libNpCppWebApi.cpp" "$E/src/src/libs/libNpCppWebApi.cpp"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/build0328.py" <<'PY'
# exp 0327's build0327.py plus one NEW unit: libNpCppWebApi.cpp is compiled with libC.cpp's command (the same flags,
# the source and the object swapped) and its object is added to the link line next to libC's. Then two test programs.
import json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build, test_sync, test_np = sys.argv[1:7]
UNITS = {
    "src/kernel/syncOnAddress.cpp": "src/CMakeFiles/kyty_emulator.dir/kernel/syncOnAddress.cpp.o",
    "src/libs/libKernel.cpp":       "src/CMakeFiles/kyty_emulator.dir/libs/libKernel.cpp.o",
    "src/kernel/fileSystem.cpp":    "src/CMakeFiles/kyty_emulator.dir/kernel/fileSystem.cpp.o",
    "src/libs/libC.cpp":            "src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o",
    "src/loader/runtimeLinker.cpp": "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o",
    "src/libs/libs.cpp":            "src/CMakeFiles/kyty_emulator.dir/libs/libs.cpp.o",
}
NEW_UNIT = "src/libs/libNpCppWebApi.cpp"   # compiled with libC.cpp's command
db = json.load(open(db_path))
def run(argv, check=True):
    print("+", " ".join(argv)[:220], "...", flush=True)
    return subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=check)
def clean_compile(cmd):
    argv = shlex.split(cmd)
    clean, skip = [], 0
    for a in argv:
        if skip: skip -= 1; continue
        if a in ("-MT", "-MF"): skip = 1; continue
        if a == "-MD": continue
        clean.append(a)
    return clean
objs, link, flags_sync, flags_libc = {}, None, None, None
for e in db:
    out = e.get("output", "")
    for rel, unit in UNITS.items():
        if out == unit:
            obj = os.path.join(out_dir, "obj", os.path.basename(rel) + ".o")
            clean = clean_compile(e["command"])
            clean[clean.index("-o") + 1] = obj
            clean[clean.index("-c") + 1] = os.path.join(src_root, rel)
            clean.insert(1, "-I" + os.path.join(src_root, "src"))
            run(clean)
            objs[unit] = obj
            if rel.endswith("syncOnAddress.cpp"): flags_sync = clean
            if rel.endswith("libC.cpp"): flags_libc = clean
    if out == "src/kyty_emulator":
        link = e["command"]
assert len(objs) == len(UNITS), f"compiled {len(objs)} of {len(UNITS)} units"
assert link is not None and flags_libc is not None
new_obj = os.path.join(out_dir, "obj", "libNpCppWebApi.cpp.o")
nc = list(flags_libc)
nc[nc.index("-o") + 1] = new_obj
nc[nc.index("-c") + 1] = os.path.join(src_root, NEW_UNIT)
run(nc)
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = 0
for k, a in enumerate(argv):
    if a in objs: argv[k] = objs[a]; nu += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert nu == len(UNITS), f"units replaced {nu} times"
libc_obj = objs["src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o"]
argv.insert(argv.index(libc_obj) + 1, new_obj)
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
run(argv)
print("== emulator linked", flush=True)
cxx = argv[0]
libs = [a for a in argv if a.startswith("-l") or a.startswith("-L") or a.endswith(".a") or a.endswith(".so") or a.startswith("-Wl,-rpath") or a.startswith("-pthread")]
all_objs = [objs.get(a, a) for a in argv if a.endswith(".o") and not a.endswith("/main.cpp.o")]
common_objs = [a for a in argv if a.endswith(".o") and ("/common/threads.cpp.o" in a or "/common/logging/" in a or "/common/common.cpp.o" in a or "/common/hostException.cpp.o" in a or "/common/assert.cpp.o" in a)]
def build_test(name, src, flags, own_objs):
    obj = os.path.join(out_dir, "obj", os.path.basename(src) + ".o")
    tc = list(flags); tc[tc.index("-o") + 1] = obj; tc[tc.index("-c") + 1] = src
    run(tc)
    bin_ = os.path.join(out_dir, name)
    r = run([cxx, "-o", bin_, obj] + own_objs + common_objs + ["-lpthread"], check=False)
    if r.returncode != 0:
        print("== minimal link of", name, "failed; linking with every shared object but main's", flush=True)
        rest = [o for o in all_objs if o not in own_objs]
        r = run([cxx, "-o", bin_, obj] + rest + own_objs + libs + ["-lpthread"], check=False)
        if r.returncode != 0:
            print("== TEST LINK FAILED:", name, flush=True); return 3
    r = run([bin_], check=False)
    print("==", name, "exit", r.returncode, flush=True)
    return 0 if r.returncode == 0 else 4
rc1 = build_test("sync_on_address_tests", test_sync, flags_sync, [objs["src/CMakeFiles/kyty_emulator.dir/kernel/syncOnAddress.cpp.o"]])
rc2 = build_test("np_cpp_web_api_tests", test_np, flags_libc, [new_obj])
sys.exit(rc1 or rc2)
PY
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then
  OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"
fi
echo "== $(date +%T) compile + link + tests"
cp "$HERE/SyncOnAddressTests.cpp" "$E/SyncOnAddressTests.cpp" 2>/dev/null; cp "$HERE/NpCppWebApiTests.cpp" "$E/NpCppWebApiTests.cpp" 2>/dev/null
distrobox enter ubuntu -- python3 -I "$E/build0328.py" "$E/compdb.json" "$E/src" "$E" "$B" "$E/SyncOnAddressTests.cpp" "$E/NpCppWebApiTests.cpp" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) build rc $rc"
grep -n "error:\|FAILED\|== .* exit\|== emulator linked\|== minimal link" "$R/build.out" | head -30
grep -c "warning:" "$R/build.out" | sed 's/^/warnings: /'
grep -a "SyncOnAddressTests:\|NpCppWebApiTests:" "$R/build.out" > "$R/tests.out"; grep -a "all checks\|FAILED" "$R/tests.out"
[ -x "$BIN" ] || { echo "no emulator built"; exit 1; }
ls -la "$BIN"; m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: 0327's six units + libs.cpp + libNpCppWebApi.cpp + shared objects ($EXPECT_NORMAL) + archive $(m "$ARCH"); tests rc $rc" >> "$R/binaries.txt"
echo "strings: NpCppWebApi lines $(strings "$BIN" | grep -c 'NpCppWebApi: not reachable'), stub lines $(strings "$BIN" | grep -c 'stubbed import')"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL)"
[ $rc = 0 ] || { echo "the tests did not pass (rc $rc): see $R/build.out and $R/tests.out"; exit $rc; }
