#!/usr/bin/env bash
# Fedora GCC does not default to PIE; RPCSX links bin/rpcsx at 0x700000000000,
# so every object (including the bundled FFmpeg, built by its own configure)
# must be position independent.
cd ~/src/rpcsx
start=$(date +%s)
echo "rpcsx commit: $(git log -1 --format=%H)"
distrobox enter fedora -- bash -c "cd ~/src/rpcsx/3rdparty/FFmpeg && true; cd ~/src/rpcsx && export CFLAGS=-fPIE && cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXE_LINKER_FLAGS=-Wl,--no-relax -DCMAKE_C_FLAGS=-fPIE \"-DCMAKE_CXX_FLAGS=-march=native -fPIE\" > /dev/null && cmake --build build -j8"
rc=$?
echo "build exit $rc after $(( $(date +%s) - start )) s"
