#!/usr/bin/env bash
# BC5 experiment 0352 (from exp 0346 build0346.sh): one private emulator, ~/bc5-work/exp0352/kyty_emulator — the backend of
# experiment 0346 (bc5/host_indirect: a GFX-form DISPATCH_INDIRECT without a SET_BASE of its type in its IB resolved and verified by the host
# else NOP-ed; BC5_DIRECT_HOST_INDIRECT, default off) built as a private archive from this experiment's copy of backend/, its
# unit tests (Catch2) built and run, then the INTEGRATED shared normal build's link command (ninja compdb) run again with
# the private archive in place of ~/bc5-work/backend-ubuntu/libbc5_backend.a (44ba4435, main d0c2668) — the emulator's
# objects are the shared ones (ddfb9456, exp 0342). A previous kyty_emulator is kept under its md5. Nothing shared is
# written; ~/src/KytyPlus, the shared build and the shared archive are only read. Catch2 comes from an earlier test
# build's FetchContent cache when one exists (no network needed), else FetchContent fetches it.
# usage: build0346.sh   (on the box, with backend/ beside it; CPU only, nice 19, under the BOX-LOCK; no emulator; ~3 min)
set -u
E=$HOME/bc5-work/exp0352; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HERE/backend; BB=$E/backend-build
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && ! grep -q "^bvh exp 0352 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop (EXPECT_ARCHIVE=... to accept)"; exit 1; }
[ -f "$SRC/CMakeLists.txt" ] && [ -f "$SRC/tests/indirect_check_batch_test.cpp" ] || { echo "no backend/ with the 0352 test beside this script"; exit 1; }
echo "bvh exp 0352 | build of ~/bc5-work/exp0352/kyty_emulator (a private backend archive + its tests, the shared emulator relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0352 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH")"
  for f in src/direct.cpp src/host_indirect.cpp include/bc5/host_indirect.hpp src/indirect_check.cpp src/shadow_labels.cpp src/policy.cpp include/bc5/policy.hpp include/bc5/direct.hpp include/bc5/indirect_check.hpp include/bc5/shadow_labels.hpp; do echo "  backend/$f $(m "$SRC/$f")"; done; } > "$R/build-inputs.txt"
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$SRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -20
[ $rc = 0 ] && [ -f "$BB/libbc5_backend.a" ] || { echo "backend build failed: see $R/backend-build.out"; exit 1; }
echo "private archive $(m "$BB/libbc5_backend.a") (shared $(m "$ARCH"))"
echo "== $(date +%T) backend tests"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -4 "$R/backend-tests.out"; echo "== tests rc $trc"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
echo "== $(date +%T) compdb + relink"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
cat > "$E/relink0352.py" <<'PY'
# the shared normal build's link command with the shared archive swapped for the private one (nothing recompiled)
import json, os, shlex, subprocess, sys
db_path, build, shared_archive, private_archive, out_bin = sys.argv[1:6]
link = next(e["command"] for e in json.load(open(db_path)) if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
n = 0
for k, a in enumerate(argv):
    if a == shared_archive: argv[k] = private_archive; n += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + out_bin + ".map"
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + out_bin + ".d"
assert n == 1, f"the shared archive appears {n} times in the link command"
argv[argv.index("-o") + 1] = out_bin
print("+", " ".join(argv)[:300], "...", flush=True)
sys.exit(subprocess.run(["nice", "-n", "19"] + argv, cwd=build).returncode)
PY
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
distrobox enter ubuntu -- python3 -I "$E/relink0352.py" "$E/compdb.json" "$B" "$ARCH" "$BB/libbc5_backend.a" "$BIN" > "$R/relink.out" 2>&1
lrc=$?; echo "== $(date +%T) relink rc $lrc"; grep -n "error\|undefined" "$R/relink.out" | head -10
[ $lrc = 0 ] && [ -x "$BIN" ] || { echo "relink failed: see $R/relink.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one: the archive did not take"; exit 1; }
echo "strings: 0352 switch line $(strings "$BIN" | grep -c 'experiment 0352 switch'), 0352 close line $(strings "$BIN" | grep -c 'experiment 0352 %s'), 0349 switch line $(strings "$BIN" | grep -c 'experiment 0349: a job'), 0346 switch line $(strings "$BIN" | grep -c 'experiment 0346 switch')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) + the private archive $(m "$BB/libbc5_backend.a") (experiment 0352: the batched CP check behind BC5_DIRECT_GPU_CHECK_BATCH, on main 9bd60be + ade0735); tests rc $trc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE)"
