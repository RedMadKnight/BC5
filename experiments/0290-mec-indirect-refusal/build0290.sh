#!/usr/bin/env bash
# BC5 experiment 0290: a private backend archive with the compute-ring refusal of DISPATCH_INDIRECT (backend/src/policy.cpp),
# and a private emulator relinked against it. Nothing shared is written: not ~/src/KytyPlus, not ~/src/bc5, not the shared
# builds, not ~/bc5-work/backend-ubuntu, not exp 0284's twin directory (it is only the model for the configuration).
#   1. ~/bc5-work/exp0290/src/backend = main's backend/ as the box's checkout ~/src/bc5 has it, plus the three files of this
#      experiment (policy.cpp, policy.hpp, policy_test.cpp) copied in by hand before the build (scp from the laptop).
#   2. ~/bc5-work/exp0290/build: configured as exp 0284's twin (Ninja, Release, -O3 -DNDEBUG, clang++, BC5_WITH_AMDGPU=ON,
#      BC5_BUILD_TESTS=OFF: Catch2 is fetched from the network, which the box build does not do), target bc5_backend.
#   3. the emulator: the shared normal build's link command (ninja -t compdb -x) with libbc5_backend.a swapped for the
#      private one and the output in ~/bc5-work/exp0290/; every object is the shared build's as it is at link time.
# usage: build0290.sh   (on the box, inside the ubuntu distrobox commands; CPU only, nice 19, under the BOX-LOCK)
set -u
E=$HOME/bc5-work/exp0290; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
SRC=$HOME/src/bc5; B=$HOME/bc5-work/kytyplus-build; SHARED_A=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
mkdir -p "$R" "$E/src" "$E/build"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
for f in policy.cpp policy.hpp policy_test.cpp; do [ -s "$E/$f" ] || { echo "missing $E/$f (scp them first)"; exit 1; }; done
echo "bvh exp 0290 | build of a private backend archive + relink of ~/bc5-work/exp0290/kyty_emulator (CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0290 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
{ echo "checkout $SRC $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null) ($(git -C "$SRC" status --porcelain backend | wc -l) local changes under backend/)"
  echo "shared archive $(stat -c '%y %s' "$SHARED_A") md5 $(md5sum < "$SHARED_A" | cut -c1-8)"
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"; } > "$R/build-inputs.txt"
echo "== $(date +%T) source copy"
rsync -a --delete --exclude build "$SRC/backend/" "$E/src/backend/" || exit 1
cp "$E/policy.cpp" "$E/src/backend/src/policy.cpp" && cp "$E/policy.hpp" "$E/src/backend/include/bc5/policy.hpp" && cp "$E/policy_test.cpp" "$E/src/backend/tests/policy_test.cpp" || exit 1
( cd "$E/src/backend" && for f in src/policy.cpp include/bc5/policy.hpp tests/policy_test.cpp; do echo "$f md5 $(md5sum < $f | cut -c1-8)"; done ) >> "$R/build-inputs.txt"
echo "== $(date +%T) configure + build bc5_backend"
distrobox enter ubuntu -- sh -c "cd '$E/build' && nice -n 19 cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_CXX_FLAGS_RELEASE='-O3 -DNDEBUG' -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF '$E/src/backend' && nice -n 19 cmake --build . --target bc5_backend -j4" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend rc $rc"; [ $rc = 0 ] || { tail -20 "$R/backend-build.out"; exit $rc; }
A=$E/build/libbc5_backend.a
echo "private archive $(stat -c '%s' "$A") bytes md5 $(md5sum < "$A" | cut -c1-8) (shared $(md5sum < "$SHARED_A" | cut -c1-8))" | tee -a "$R/build-inputs.txt"
echo "== $(date +%T) compdb + relink"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
cat > "$E/relink0290.py" <<'PY'
import json, os, shlex, subprocess, sys
db, a_shared, a_priv, out_dir, build = sys.argv[1:6]
link = next(e["command"] for e in json.load(open(db)) if e.get("output") == "src/kyty_emulator")
argv = [a for a in shlex.split(link) if a not in (":", "&&")]
n = 0
for k, a in enumerate(argv):
    if a == a_shared or a.endswith("/libbc5_backend.a"):
        argv[k] = a_priv; n += 1
    elif a.startswith("-Wl,-Map="): argv[k] = "-Wl,-Map=" + os.path.join(out_dir, "kyty_emulator.map")
    elif a.startswith("--dependency-file="): argv[k] = "--dependency-file=" + os.path.join(out_dir, "link.d")
assert n == 1, f"{n} archive arguments replaced"
argv[argv.index("-o") + 1] = os.path.join(out_dir, "kyty_emulator")
print("+", " ".join(argv)[:200], "...", flush=True)
subprocess.run(["nice", "-n", "19"] + argv, cwd=build, check=True)
PY
distrobox enter ubuntu -- python3 -I "$E/relink0290.py" "$E/compdb.json" "$SHARED_A" "$A" "$E" "$B" > "$R/relink.out" 2>&1
rc=$?; echo "== $(date +%T) relink rc $rc"; [ $rc = 0 ] || { tail -20 "$R/relink.out"; exit $rc; }
BIN=$E/kyty_emulator
ls -la "$BIN"; md5sum < "$BIN" | cut -c1-8 > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5")"
echo "refusal string: $(strings "$BIN" | grep -c 'MEC check unverified')"
echo "shared binary after: $(md5sum < "$B/src/kyty_emulator" | cut -c1-8); shared archive after: $(md5sum < "$SHARED_A" | cut -c1-8)"
