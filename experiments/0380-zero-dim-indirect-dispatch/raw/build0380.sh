#!/usr/bin/env bash
# BC5 experiment 0380, box step A0: a CPU-only compile check of this branch's backend with libdrm
# (BC5_WITH_AMDGPU=ON, clang as bc5-build.sh builds the shared archive) in the `ubuntu` distrobox, into ~/bc5-work/exp0380/backend-build, then its
# Catch2 tests. No emulator, no --submit, nothing on the GPU; the shared archive
# (~/bc5-work/backend-ubuntu), the shared builds and play-pkg.sh are not touched.
# Input: the branch's backend/ unpacked into ~/bc5-work/exp0380/in/backend (git archive from the laptop).
# The caller holds the BOX-LOCK line "top exp 0380 | ..." (written and cleared by the laptop's ssh).
# usage: bash ~/bc5-work/exp0380/in/raw/build0380.sh
set -u
E=$HOME/bc5-work/exp0380; IN=$E/in; BB=$E/backend-build; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q "^top exp 0380 |" "$LOCK" 2> /dev/null || { echo "the lock line is not exp 0380's: stop ($(cat "$LOCK" 2> /dev/null))"; exit 1; }
rm -rf "$BB"  # this experiment's own build directory, always fresh
[ -f "$IN/backend/CMakeLists.txt" ] || { echo "no backend/ in $IN"; exit 1; }
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | grep -v exp0380 | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) configure"
distrobox enter ubuntu -- bash -c "cd '$IN' && nice -n 19 cmake -S backend -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG" > "$R/configure.log" 2>&1 \
    || { tail -20 "$R/configure.log"; echo "configure FAILED"; exit 1; }
echo "== $(date +%T) build"
distrobox enter ubuntu -- bash -c "nice -n 19 cmake --build '$BB' -j 6" > "$R/build.log" 2>&1 \
    || { grep -E "error|warning" "$R/build.log" | head -30; echo "build FAILED"; exit 1; }
echo "warnings: $(grep -c 'warning:' "$R/build.log")"
echo "== $(date +%T) tests"
distrobox enter ubuntu -- bash -c "cd '$BB' && nice -n 19 ./bc5_backend_tests '[indirect_check]' && nice -n 19 ./bc5_backend_tests" > "$R/tests.log" 2>&1
rc=$?
tail -4 "$R/tests.log"
{ echo "toolchain: $(distrobox enter ubuntu -- bash -c 'clang++ --version | head -1; cmake --version | head -1' 2> /dev/null | tr '\n' ' ')"
  echo "archive $(md5sum < "$BB/libbc5_backend.a" | cut -c1-8)  direct-selftest $(ls "$BB"/direct-selftest > /dev/null 2>&1 && echo built || echo missing)  tests rc $rc"; } | tee "$R/summary.txt"
exit $rc
