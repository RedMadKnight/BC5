#!/usr/bin/env bash
# BC5 experiment 0327: one private emulator, ~/bc5-work/exp0327/kyty_emulator, from the shared normal build's objects
# (ninja -t compdb -x gives the compile and link commands) with SIX units replaced: the files patch0327.py makes from the
# tree ~/src/KytyPlus (f266548 + patch 0001, as the box has it) — src/kernel/syncOnAddress.cpp, src/libs/libKernel.cpp,
# src/kernel/fileSystem.cpp, src/libs/libC.cpp, src/loader/runtimeLinker.cpp (the headers syncOnAddress.h and
# fileSystem.h change their declarations only; the other units' objects are kept). The backend archive: the shared one
# (825ae1d1 since exp 0323 — exp 0290's refusal), md5-checked. Then the sync-on-address tests (SyncOnAddressTests.cpp,
# after upstream's) are built against the patched unit and run; a failing test stops the script after the emulator was
# linked (the binary is kept, the failure printed). A previous kyty_emulator is kept beside the new one under its md5.
# Nothing shared is written; ~/src/KytyPlus is read. The headers are taken from the patched copy through -I<out>/src
# ahead of the tree's includes, so the six units see the new declarations.
# usage: build0327.sh   (on the box; CPU only, nice 19, under the BOX-LOCK; no emulator runs; ~2 min)
set -u
E=$HOME/bc5-work/exp0327; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
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
for f in patch0327.py SyncOnAddressTests.cpp; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
echo "bvh exp 0327 | build of ~/bc5-work/exp0327/kyty_emulator (six units compiled + relink against the shared objects; the sync-on-address tests; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0327 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "tree $(cd "$K" && git log -1 --format=%h 2>/dev/null) bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp")"
  for f in src/kernel/syncOnAddress.h src/kernel/syncOnAddress.cpp src/libs/libKernel.cpp src/kernel/fileSystem.h src/kernel/fileSystem.cpp src/libs/libC.cpp src/loader/runtimeLinker.cpp; do echo "  $f $(m "$K/$f")"; done
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH")"; } > "$R/build-inputs.txt"
echo "== $(date +%T) patch"
[ "$HERE/patch0327.py" -ef "$E/patch0327.py" ] || cp "$HERE/patch0327.py" "$E/patch0327.py"
distrobox enter ubuntu -- python3 -I "$E/patch0327.py" "$K" "$E/src" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "patch0327.py failed"; exit 1; }
cat "$R/patch.out"
cp "$E/src/patch_0327.diff" "$R/patch_0327.diff"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/build0327.py" <<'PY'
# exp 0321's build0321.py for several units: compile each patched unit with the shared build's flags (the patched
# headers first on the include path), link with the shared objects (the units' objects swapped), the map and the
# dependency file into the private directory. Then the sync-on-address tests: the test TU + the patched unit, linked
# with the shared common objects (threads, logging); on a link failure, with every shared object but main's.
import json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build, test_src = sys.argv[1:6]
UNITS = {
    "src/kernel/syncOnAddress.cpp": "src/CMakeFiles/kyty_emulator.dir/kernel/syncOnAddress.cpp.o",
    "src/libs/libKernel.cpp":       "src/CMakeFiles/kyty_emulator.dir/libs/libKernel.cpp.o",
    "src/kernel/fileSystem.cpp":    "src/CMakeFiles/kyty_emulator.dir/kernel/fileSystem.cpp.o",
    "src/libs/libC.cpp":            "src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o",
    "src/loader/runtimeLinker.cpp": "src/CMakeFiles/kyty_emulator.dir/loader/runtimeLinker.cpp.o",
}
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
objs, link, flags_for_test = {}, None, None
for e in db:
    out = e.get("output", "")
    for rel, unit in UNITS.items():
        if out == unit:
            obj = os.path.join(out_dir, "obj", os.path.basename(rel) + ".o")
            clean = clean_compile(e["command"])
            clean[clean.index("-o") + 1] = obj
            clean[clean.index("-c") + 1] = os.path.join(src_root, rel)
            clean.insert(1, "-I" + os.path.join(src_root, "src"))  # the patched headers first
            run(clean)
            objs[unit] = obj
            if rel.endswith("syncOnAddress.cpp"):
                flags_for_test = clean
    if out == "src/kyty_emulator":
        link = e["command"]
assert len(objs) == len(UNITS), f"compiled {len(objs)} of {len(UNITS)} units"
assert link is not None, "no link command"
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = 0
for k, a in enumerate(argv):
    if a in objs: argv[k] = objs[a]; nu += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert nu == len(UNITS), f"units replaced {nu} times"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
run(argv)
print("== emulator linked", flush=True)
# the tests
test_obj = os.path.join(out_dir, "obj", "SyncOnAddressTests.cpp.o")
tc = list(flags_for_test)
tc[tc.index("-o") + 1] = test_obj
tc[tc.index("-c") + 1] = test_src
run(tc)
cxx = argv[0]
sync_obj = objs["src/CMakeFiles/kyty_emulator.dir/kernel/syncOnAddress.cpp.o"]
common_objs = [a for a in argv if a.endswith(".o") and ("/common/threads.cpp.o" in a or "/common/logging/" in a or "/common/common.cpp.o" in a or "/common/hostException.cpp.o" in a)]
test_bin = os.path.join(out_dir, "sync_on_address_tests")
r = run([cxx, "-o", test_bin, test_obj, sync_obj] + common_objs + ["-lpthread"], check=False)
if r.returncode != 0:
    print("== minimal test link failed; linking with every shared object but main's", flush=True)
    all_objs = [objs.get(a, a) for a in argv if a.endswith(".o") and not a.endswith("/main.cpp.o")]
    libs = [a for a in argv if a.startswith("-l") or a.startswith("-L") or a.endswith(".a") or a.endswith(".so") or a.startswith("-Wl,-rpath") or a.startswith("-pthread")]
    r = run([cxx, "-o", test_bin, test_obj] + [o for o in all_objs if o != sync_obj] + [sync_obj] + libs + ["-lpthread"], check=False)
    if r.returncode != 0:
        print("== TEST LINK FAILED (the emulator is built; the tests are not)", flush=True)
        sys.exit(3)
r = run([test_bin], check=False)
print("== tests exit", r.returncode, flush=True)
sys.exit(0 if r.returncode == 0 else 4)
PY
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then
  OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"
fi
echo "== $(date +%T) compile + link + tests"
cp "$HERE/SyncOnAddressTests.cpp" "$E/SyncOnAddressTests.cpp"
distrobox enter ubuntu -- python3 -I "$E/build0327.py" "$E/compdb.json" "$E/src" "$E" "$B" "$E/SyncOnAddressTests.cpp" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) build rc $rc"
grep -n "error:\|Error\|FAILED\|== tests exit\|== emulator linked\|== minimal test link failed" "$R/build.out" | head -30
grep -c "warning:" "$R/build.out" | sed 's/^/warnings: /'
grep -a "SyncOnAddressTests:" "$R/build.out" > "$R/tests.out"; tail -3 "$R/tests.out"
[ -x "$BIN" ] || { echo "no emulator built"; exit 1; }
ls -la "$BIN"; m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: six units + shared objects ($EXPECT_NORMAL) + archive $(m "$ARCH"); tests rc $rc" >> "$R/binaries.txt"
echo "strings: the twelve NIDs' names in the binary: $(strings "$BIN" | grep -c 'sceKernelSyncOnAddressWait8\|sceKernelSyncOnAddressWait16'), stub lines $(strings "$BIN" | grep -c '\[bc5\] stubbed import')"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL)"
[ $rc = 0 ] || { echo "the tests did not pass (rc $rc): see $R/build.out and $R/tests.out"; exit $rc; }
