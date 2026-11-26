#!/usr/bin/env bash
# BC5 exp 0439 (tag pa439): test_pa0439.cpp in the ubuntu distrobox, then both planted bugs (must FAIL). CPU only.
set -u
H=$HOME/bc5-work/exp0439/k439; T=$H/tpa
rm -rf "$T"; mkdir -p "$T/bc5" && cp "$H/pa0439.hpp" "$T/bc5/" && cp "$H/test_pa0439.cpp" "$T/" || exit 1
distrobox enter ubuntu -- bash -c "cd '$T' && g++ -std=c++20 -O1 -Wall -Wextra -I. test_pa0439.cpp -o t && ./t; \
 for p in READ DMA; do g++ -std=c++20 -O1 -DBC5_PA439_PLANT_\$p -I. test_pa0439.cpp -o tp && echo \"plant \$p: \$(./tp | tail -1)\"; done"
