#!/usr/bin/env bash
# BC5 experiment 0380 (F617): the morning-candidates binary, ~/bc5-work/exp0380arms/bin/kyty_emulator =
#   the shared normal build's objects (58c4a627)
#   + a PRIVATE backend archive from this branch's backend/ (backend.tar, git archive of the given commit),
#     configured as the shared one (clang, Release, BC5_WITH_AMDGPU=ON); its Catch2 suite is built and run in a
#     second directory first, and the emulator is linked only when it passes. It holds every exp 0380 switch,
#     default off: ARGS_COPY into the low-VA slot (F574), ARGS_WB, ARGS_FLUSH / ARGS_FLUSH_DRAWS (F617), ...
#   + bc5LleAgc.cpp and runtimeLinker.cpp exactly as in build0380r1.sh (exp 0379's skip, the F608 recorder,
#     BC5_CRASH_FRAMES).
# The host includes no backend header these changes touch (only indirect_check.hpp changed, which no host file
# includes), so the shared objects link with the private archive. ~/src/KytyPlus, the shared builds, the shared
# archive and play-pkg.sh are only read. CPU only, nice 19, no emulator.
# usage: bash ~/bc5-work/exp0380arms/build0380arms.sh <commit>   (backend.tar of that commit, build0380y.py,
#        mk-rec0380.py, rec0380.inc, mk-crash0380.py beside it)
set -u
COMMIT=${1:?the backend commit}
W=$HOME/bc5-work; E=$W/exp0380arms; R=$E/raw; LOCK=$W/BOX-LOCK; B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus
ARCH=$W/backend-ubuntu/libbc5_backend.a; Z=$W/exp0379t/src/src
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
grep -q '^top exp 0380 |' "$LOCK" || { echo "the lock line is not this session's: $(cat "$LOCK")"; exit 1; }
mkdir -p "$R" "$E/src/libs/bc5" "$E/src/loader" "$E/bin" "$E/obj"
RL=$TREE/src/loader/runtimeLinker.cpp
pins() { echo "shared normal $(m "$B/src/kyty_emulator") lean $(m "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m "$ARCH") tree unit $(m "$TREE/src/libs/bc5LleAgc.cpp") play-pkg.sh $(m "$W/play-pkg.sh")"; }
P0=$(pins); echo "before: $P0" | tee "$R/build-pins.txt"
[ "$P0" = "shared normal 58c4a627 lean dcbeb440 archive bb50b2e0 tree unit e7cc2f60 play-pkg.sh 55531ab6" ] || { echo "a shared pin differs: stop"; exit 1; }
[ "$(m "$RL")" = 96e03695 ] && [ "$(m "$Z/libs/bc5LleAgc.cpp")" = e62113a5 ] && [ "$(m "$Z/bc5/zero_skip.hpp")" = 782ca0e9 ] || { echo "exp 0379's unit or header is not e62113a5 / 782ca0e9: stop"; exit 1; }
cp "$Z/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.0379.cpp" && cp "$Z/bc5/zero_skip.hpp" "$E/src/libs/bc5/zero_skip.hpp" || exit 1
python3 -I "$E/mk-rec0380.py" "$E/src/bc5LleAgc.0379.cpp" "$E/rec0380.inc" "$E/src/libs/bc5LleAgc.cpp" || { echo "the recorder's edits did not apply: stop"; exit 1; }
python3 -I "$E/mk-crash0380.py" "$RL" "$E/src/loader/runtimeLinker.cpp" || { echo "the crash-frames edit did not apply: stop"; exit 1; }
echo "runtimeLinker.cpp: tree $(m "$RL") + crash frames = $(m "$E/src/loader/runtimeLinker.cpp")" | tee -a "$R/build-pins.txt"
echo "unit: 0379 $(m "$E/src/bc5LleAgc.0379.cpp") + recorder = $(m "$E/src/libs/bc5LleAgc.cpp"); ZERO_SKIP $(grep -c 'BC5_DIRECT_ZERO_SKIP' "$E/src/libs/bc5LleAgc.cpp"), rec0380( $(grep -c 'rec0380(' "$E/src/libs/bc5LleAgc.cpp")" | tee -a "$R/build-pins.txt"
BIN=$E/bin/kyty_emulator
[ -f "$BIN" ] && { echo "$BIN exists: stop"; exit 1; }
# the private archive and its tests
BM=$E/backend-src; BA=$E/backend-archive; BT=$E/backend-tests
rm -rf "$BM" "$BA" "$BT"; mkdir -p "$BM" && tar -xf "$E/backend.tar" -C "$BM" || exit 1
echo "backend: commit $COMMIT, tar $(m "$E/backend.tar"); ARGS_FLUSH in direct.cpp $(grep -c 'BC5_DIRECT_ARGS_FLUSH' "$BM/backend/src/direct.cpp")" | tee -a "$R/build-pins.txt"
CATCH=$(ls -d "$W"/exp03*/backend-tests/_deps/catch2-src "$W"/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH"
distrobox enter ubuntu -- sh -c "nice -n 19 cmake -S '$BM/backend' -B '$BT' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BT' -j8" > "$R/backend-tests-build.out" 2>&1 || { tail -20 "$R/backend-tests-build.out"; echo "the backend tests did not build: stop"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BT' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1; trc=$?
echo "Catch2 rc $trc: $(tail -2 "$R/backend-tests.out" | tr '\n' ' '); warnings $(grep -c 'warning:' "$R/backend-tests-build.out")" | tee -a "$R/build-pins.txt"
[ $trc = 0 ] || { echo "backend tests FAILED: no emulator linked"; exit 2; }
distrobox enter ubuntu -- sh -c "nice -n 19 cmake -S '$BM/backend' -B '$BA' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF && nice -n 19 cmake --build '$BA' --target bc5_backend -j8" > "$R/archive-build.out" 2>&1 || { tail -20 "$R/archive-build.out"; echo "the archive did not build: stop"; exit 1; }
PARCH=$BA/libbc5_backend.a
echo "private archive $(m "$PARCH"), warnings $(grep -c 'warning:' "$R/archive-build.out")" | tee -a "$R/build-pins.txt"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$E/build0380y.py" "$E/compdb.json" "$B" "$E/obj" "$BIN" "--archive=$PARCH" "libs/bc5LleAgc.cpp.o=$E/src/libs/bc5LleAgc.cpp=$TREE/src/libs" "loader/runtimeLinker.cpp.o=$E/src/loader/runtimeLinker.cpp=$TREE/src/loader" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
echo "binary $(m "$BIN"); strings: zero skip $(strings "$BIN" | grep -c '^zero skip: '), rec0380 $(strings "$BIN" | grep -c 'rec0380: '), BC5_0380_REC $(strings "$BIN" | grep -c '^BC5_0380_REC$'), BC5_DIRECT_ZERO_SKIP $(strings "$BIN" | grep -c '^BC5_DIRECT_ZERO_SKIP$'), PIECES_NO_CLEAR $(strings "$BIN" | grep -c '^BC5_DIRECT_PIECES_NO_CLEAR$'), CRASH_FRAMES $(strings "$BIN" | grep -c '^BC5_CRASH_FRAMES$'), REC_RING $(strings "$BIN" | grep -c '^BC5_0380_REC_RING$'), ARGS_FLUSH $(strings "$BIN" | grep -c '^BC5_DIRECT_ARGS_FLUSH$'), ARGS_COPY $(strings "$BIN" | grep -c '^BC5_DIRECT_ARGS_COPY$')" | tee -a "$R/build-pins.txt"
grep -n "warning:" "$R/build.out" | sed 's/^.*bc5LleAgc.cpp:\([0-9]*\).*\[\(-W[^]]*\)\].*$/line \1 \2/' | tee -a "$R/build-pins.txt"
P1=$(pins); echo "after: $P1" | tee -a "$R/build-pins.txt"
[ "$P1" = "$P0" ] || { echo "A SHARED PIN CHANGED"; exit 1; }
