#!/usr/bin/env bash
# BC5 experiment 0329: one private emulator, ~/bc5-work/exp0329/kyty_emulator, carrying exp 0327's twelve imports, exp
# 0328's NpCppWebApi port AND the remaining 61 imports of exp 0329, from the shared normal build's objects: patch0329.py
# (0328's eight files + fifteen more) applied to the tree ~/src/KytyPlus (f266548 + patch 0001), the five new units
# copied in beside them (libNpCppWebApi.cpp of 0328; libPngEnc.cpp, libPlayGoDialog.cpp, libNpCommerceDialog.cpp,
# libPlayerInvitationDialog.cpp of 0329), SIXTEEN patched units compiled with the shared flags (four at a time, the
# patched headers first), relinked against the shared objects and the shared archive (825ae1d1); then the four test
# programs (sync-on-address of 0327, NpCppWebApi of 0328, PngEnc and the dialogs of 0329) built against the patched
# units and run — a failing test ends the script after the emulator was linked. A previous kyty_emulator is kept under
# its md5. Nothing shared is written; ~/src/KytyPlus is read.
# usage: build0329.sh   (on the box; CPU only, nice 19, under the BOX-LOCK; no emulator runs; ~4 min)
set -u
E=$HOME/bc5-work/exp0329; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; K=$HOME/src/KytyPlus; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-825ae1d1}; EXPECT_NORMAL=${EXPECT_NORMAL:-5dd77a82}
HERE=$(cd "$(dirname "$0")" && pwd)
NEW_UNITS="libNpCppWebApi.cpp libPngEnc.cpp libPlayGoDialog.cpp libNpCommerceDialog.cpp libPlayerInvitationDialog.cpp"
TESTS="SyncOnAddressTests.cpp NpCppWebApiTests.cpp PngEncTests.cpp DialogsTests.cpp"
mkdir -p "$R" "$E/src" "$E/obj"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 5bccbb80 ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80 (the tree changed): stop"; exit 1; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop (EXPECT_ARCHIVE=... to accept)"; exit 1; }
for f in patch0329.py $NEW_UNITS $TESTS; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
echo "bvh exp 0329 | build of ~/bc5-work/exp0329/kyty_emulator (sixteen units compiled + five new + relink against the shared objects; four test programs; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0329 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "tree $(cd "$K" && git log -1 --format=%h 2>/dev/null) bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp")"
  for f in src/kernel/syncOnAddress.h src/kernel/syncOnAddress.cpp src/libs/libKernel.cpp src/kernel/fileSystem.h src/kernel/fileSystem.cpp src/libs/libC.cpp src/loader/runtimeLinker.cpp src/libs/libs.cpp src/kernel/memory.h src/kernel/memory.cpp src/libs/network.h src/libs/network.cpp src/libs/libNet.cpp src/libs/libSaveData.cpp src/libs/audio.h src/libs/audio.cpp src/libs/libAudio.cpp src/libs/controller.h src/libs/controller.cpp src/libs/libPad.cpp src/graphics/presentation/videoOut.h src/graphics/presentation/videoOut.cpp src/libs/libVideoOut.cpp; do echo "  $f $(m "$K/$f")"; done
  for f in $NEW_UNITS; do echo "  $f (new) $(m "$HERE/$f")"; done
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH")"; } > "$R/build-inputs.txt"
echo "== $(date +%T) patch"
[ "$HERE/patch0329.py" -ef "$E/patch0329.py" ] || cp "$HERE/patch0329.py" "$E/patch0329.py"
distrobox enter ubuntu -- python3 -I "$E/patch0329.py" "$K" "$E/src" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "patch0329.py failed"; exit 1; }
cat "$R/patch.out"
cp "$E/src/patch_0329.diff" "$R/patch_0329.diff"
cp "$K"/src/kernel/*.inc "$E/src/src/kernel/"   # memory.cpp includes a generated .inc of its own directory
mkdir -p "$E/src/src/libs" && for f in $NEW_UNITS; do cp "$HERE/$f" "$E/src/src/libs/$f"; done
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/build0329.py" <<'PY'
# exp 0328's build0328.py generalised: the patched units are compiled four at a time with their own compile commands
# from the compdb (the patched headers first via -I<out>/src); each NEW unit is compiled with libC.cpp's command (the
# same flags, the source and the object swapped) and its object is added to the link line next to libC's. Then the
# test programs, each linked with its own objects plus the common ones, or — when that falls short of fmt and the
# symbol database — with every shared object but main's.
import concurrent.futures, json, os, shlex, subprocess, sys
db_path, src_root, out_dir, build = sys.argv[1:5]
tests = sys.argv[5:]
UNITS = {rel: "src/CMakeFiles/kyty_emulator.dir/" + rel[len("src/"):] + ".o" for rel in [
    "src/kernel/syncOnAddress.cpp", "src/libs/libKernel.cpp", "src/kernel/fileSystem.cpp", "src/libs/libC.cpp",
    "src/loader/runtimeLinker.cpp", "src/libs/libs.cpp", "src/kernel/memory.cpp", "src/libs/network.cpp",
    "src/libs/libNet.cpp", "src/libs/libSaveData.cpp", "src/libs/audio.cpp", "src/libs/libAudio.cpp",
    "src/libs/controller.cpp", "src/libs/libPad.cpp", "src/graphics/presentation/videoOut.cpp", "src/libs/libVideoOut.cpp"]}
NEW_UNITS = ["src/libs/libNpCppWebApi.cpp", "src/libs/libPngEnc.cpp", "src/libs/libPlayGoDialog.cpp",
             "src/libs/libNpCommerceDialog.cpp", "src/libs/libPlayerInvitationDialog.cpp"]   # compiled with libC.cpp's command
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
objs, link, flags_sync, flags_libc, jobs = {}, None, None, None, []
for e in db:
    out = e.get("output", "")
    for rel, unit in UNITS.items():
        if out == unit:
            obj = os.path.join(out_dir, "obj", os.path.basename(rel) + ".o")
            clean = clean_compile(e["command"])
            clean[clean.index("-o") + 1] = obj
            clean[clean.index("-c") + 1] = os.path.join(src_root, rel)
            clean.insert(1, "-I" + os.path.join(src_root, "src"))
            jobs.append(clean)
            objs[unit] = obj
            if rel.endswith("syncOnAddress.cpp"): flags_sync = clean
            if rel.endswith("libC.cpp"): flags_libc = clean
    if out == "src/kyty_emulator":
        link = e["command"]
assert len(objs) == len(UNITS), f"found {len(objs)} of {len(UNITS)} units in the compdb"
assert link is not None and flags_libc is not None
new_objs = []
for rel in NEW_UNITS:
    obj = os.path.join(out_dir, "obj", os.path.basename(rel) + ".o")
    nc = list(flags_libc)
    nc[nc.index("-o") + 1] = obj
    nc[nc.index("-c") + 1] = os.path.join(src_root, rel)
    jobs.append(nc)
    new_objs.append(obj)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda argv: run(argv, check=False).returncode, jobs))
failed = [jobs[i][jobs[i].index("-c") + 1] for i, rc in enumerate(results) if rc != 0]
if failed:
    print("== COMPILE FAILED:", " ".join(os.path.basename(f) for f in failed), flush=True); sys.exit(2)
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
nu = 0
for k, a in enumerate(argv):
    if a in objs: argv[k] = objs[a]; nu += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert nu == len(UNITS), f"units replaced {nu} times"
libc_obj = objs["src/CMakeFiles/kyty_emulator.dir/libs/libC.cpp.o"]
at = argv.index(libc_obj) + 1
for obj in new_objs:
    argv.insert(at, obj); at += 1
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
    if run(tc, check=False).returncode != 0:
        print("== TEST COMPILE FAILED:", name, flush=True); return 3
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
def test_src(base): return [t for t in tests if os.path.basename(t) == base][0]
by_name = {os.path.basename(rel): obj for rel, obj in zip(NEW_UNITS, new_objs)}
rc = 0
rc = rc or build_test("sync_on_address_tests", test_src("SyncOnAddressTests.cpp"), flags_sync, [objs["src/CMakeFiles/kyty_emulator.dir/kernel/syncOnAddress.cpp.o"]])
rc = rc or build_test("np_cpp_web_api_tests", test_src("NpCppWebApiTests.cpp"), flags_libc, [by_name["libNpCppWebApi.cpp"]])
rc = rc or build_test("png_enc_tests", test_src("PngEncTests.cpp"), flags_libc, [by_name["libPngEnc.cpp"]])
rc = rc or build_test("dialogs_tests", test_src("DialogsTests.cpp"), flags_libc, [by_name["libPlayGoDialog.cpp"], by_name["libNpCommerceDialog.cpp"], by_name["libPlayerInvitationDialog.cpp"]])
sys.exit(rc)
PY
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then
  OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"
fi
echo "== $(date +%T) compile + link + tests"
TEST_ARGS=""; for f in $TESTS; do cp "$HERE/$f" "$E/$f"; TEST_ARGS="$TEST_ARGS $E/$f"; done
# shellcheck disable=SC2086
distrobox enter ubuntu -- python3 -I "$E/build0329.py" "$E/compdb.json" "$E/src" "$E" "$B" $TEST_ARGS > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) build rc $rc"
grep -n "error:\|FAILED\|== .* exit\|== emulator linked\|== minimal link" "$R/build.out" | head -40
grep -c "warning:" "$R/build.out" | sed 's/^/warnings: /'
grep -a "SyncOnAddressTests:\|NpCppWebApiTests:\|PngEncTests:\|DialogsTests:" "$R/build.out" > "$R/tests.out"; grep -a "all checks\|FAILED" "$R/tests.out"
[ -x "$BIN" ] || { echo "no emulator built"; exit 1; }
ls -la "$BIN"; m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: sixteen patched units + five new units + shared objects ($EXPECT_NORMAL) + archive $(m "$ARCH"); tests rc $rc" >> "$R/binaries.txt"
echo "strings: NpCppWebApi lines $(strings "$BIN" | grep -c 'NpCppWebApi: not reachable'), stub lines $(strings "$BIN" | grep -c 'stubbed import'), mlock line $(strings "$BIN" | grep -c 'sceKernelMlock: the host refused')"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL)"
[ $rc = 0 ] || { echo "the build or the tests did not pass (rc $rc): see $R/build.out and $R/tests.out"; exit $rc; }
