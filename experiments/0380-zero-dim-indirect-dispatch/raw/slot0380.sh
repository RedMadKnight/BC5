#!/usr/bin/env bash
# BC5 experiment 0380 (F614): one box slot, CPU only, no emulator, never ~/src:
# 1. BUILD-01's dry test (Codex, test_build01_backup.py with build01_prepare.py's BACKUP block, unchanged) against
#    throwaway git repos under ~/bc5-work/exp0380/build01/tmp, on the host and in the ubuntu distrobox;
# 2. int/0380-to-main's backend (git archive of the int branch, int-backend.tar) configured as the shared archive
#    (clang, Release, BC5_WITH_AMDGPU=ON) with its Catch2 tests, built in ~/bc5-work/exp0380/int-check/, the suite run,
#    and direct-selftest run without --submit (it does nothing on the GPU then).
# usage: bash ~/bc5-work/exp0380/slot0380.sh   (with int-backend.tar in int-check/, the two .py files in build01/)
set -u
W=$HOME/bc5-work; E=$W/exp0380; B=$E/build01; I=$E/int-check; LOCK=$W/BOX-LOCK
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q '^top exp 0380 |' "$LOCK" || { echo "the lock line is not this session's: $(cat "$LOCK")"; exit 1; }
echo "== $(date +%T) 1. BUILD-01 dry test"
mkdir -p "$B/tmp"
cd "$B" || exit 1
echo "host: $(git --version); $(tar --version | head -1); bash $BASH_VERSION; $(python3 --version)"
TMPDIR=$B/tmp python3 test_build01_backup.py 2>&1 | tail -8
distrobox enter ubuntu -- bash -c "cd '$B' && echo \"container: \$(git --version); \$(tar --version | head -1); bash \$BASH_VERSION; \$(python3 --version)\" && TMPDIR='$B/tmp' python3 test_build01_backup.py 2>&1 | tail -8"
find "$B/tmp" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
echo "== $(date +%T) 2. int/0380-to-main backend: Catch2 and direct-selftest"
rm -rf "$I/src" "$I/build"
mkdir -p "$I/src" && tar -xf "$I/int-backend.tar" -C "$I/src" || exit 1
CATCH=$(ls -d "$W"/exp03*/backend-tests/_deps/catch2-src "$W"/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
distrobox enter ubuntu -- sh -c "nice -n 19 cmake -S '$I/src/backend' -B '$I/build' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$I/build' -j8" > "$I/build.out" 2>&1
rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$I/build.out"), warnings $(grep -c 'warning:' "$I/build.out")"
[ $rc = 0 ] || { tail -20 "$I/build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$I/build' && nice -n 19 ./bc5_backend_tests" > "$I/tests.out" 2>&1
echo "Catch2 rc $?: $(tail -3 "$I/tests.out" | tr '\n' ' ')"
for tg in indirect_check zero_skip; do distrobox enter ubuntu -- sh -c "cd '$I/build' && ./bc5_backend_tests '[$tg]'" 2>&1 | tail -2 | tr '\n' ' ' | sed "s/^/[$tg] /"; echo; done
distrobox enter ubuntu -- sh -c "cd '$I/build' && ./direct-selftest; echo rc \$?; ./direct-selftest --cp-check --zero-check; echo rc \$?"
echo "== $(date +%T) done"
