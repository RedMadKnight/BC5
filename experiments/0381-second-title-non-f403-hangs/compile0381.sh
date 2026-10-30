#!/usr/bin/env bash
# BC5 exp 0381: CPU-only compile check of this branch's backend with libdrm (BC5_WITH_AMDGPU=ON, clang, as exp 0380's
# build0380.sh) in the `ubuntu` distrobox, in a throwaway directory ~/bc5-work/exp0381cc (never ~/src), then the
# Catch2 tests. No emulator, no --submit, nothing on the GPU; the shared archive, builds and play-pkg.sh are untouched.
# From the laptop, on the top session's GO:
#   git archive HEAD backend | ssh bc250 'pgrep "^kyty_emulator" >/dev/null && exit 3; rm -rf ~/bc5-work/exp0381cc && mkdir -p ~/bc5-work/exp0381cc/in && tar -xf - -C ~/bc5-work/exp0381cc/in'
#   ssh bc250 'bash -s' < compile0381.sh
set -u
E=$HOME/bc5-work/exp0381cc; IN=$E/in; BB=$E/build
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 3; }
[ -s "$HOME/bc5-work/BOX-LOCK" ] && ! grep -q '^top exp 0381 |' "$HOME/bc5-work/BOX-LOCK" && { echo "BOX-LOCK busy: $(cat "$HOME/bc5-work/BOX-LOCK")"; exit 4; }
[ -f "$IN/backend/CMakeLists.txt" ] || { echo "no backend/ in $IN"; exit 1; }
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) configure"
distrobox enter ubuntu -- bash -c "cd '$IN' && nice -n 19 cmake -S backend -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG" < /dev/null > "$E/configure.log" 2>&1 \
    || { tail -20 "$E/configure.log"; echo "configure FAILED"; exit 1; }
echo "== $(date +%T) build"
distrobox enter ubuntu -- bash -c "nice -n 19 cmake --build '$BB' -j 6" < /dev/null > "$E/build.log" 2>&1 \
    || { grep -E "error|warning" "$E/build.log" | head -30; echo "build FAILED"; exit 1; }
echo "warnings: $(grep -c 'warning:' "$E/build.log")"
echo "== $(date +%T) tests"
distrobox enter ubuntu -- bash -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" < /dev/null > "$E/tests.log" 2>&1
rc=$?
tail -3 "$E/tests.log"
echo "toolchain: $(distrobox enter ubuntu -- bash -c 'clang++ --version | head -1' < /dev/null 2> /dev/null)  archive $(md5sum < "$BB/libbc5_backend.a" | cut -c1-8)  tests rc $rc"
exit $rc
