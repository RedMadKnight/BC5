#!/usr/bin/env bash
# RPCSX assumes a default-PIE toolchain (its CI: Ubuntu). Built in the `ubuntu`
# distrobox (Ubuntu 26.04, GCC 15 --enable-default-pie), unmodified sources.
cd ~/src/rpcsx
start=$(date +%s)
echo "rpcsx commit: $(git log -1 --format=%H)"
distrobox enter ubuntu -- bash -c "cd ~/src/rpcsx/3rdparty/FFmpeg && make distclean >/dev/null 2>&1; cd ~/src/rpcsx && cmake -B build-ubuntu -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS_INIT=-march=native > /dev/null && cmake --build build-ubuntu -j8"
rc=$?
echo "build exit $rc after $(( $(date +%s) - start )) s"
