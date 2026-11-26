#!/usr/bin/env bash
# BC5 exp 0439 (tag fa439): test_fa0439.cpp in the ubuntu distrobox, then both planted bugs (must FAIL). CPU only.
set -u
H=$HOME/bc5-work/exp0439/k439; T=$H/tfa
rm -rf "$T"; mkdir -p "$T/bc5" && cp "$H/fa0439.hpp" "$T/bc5/" && cp "$H/test_fa0439.cpp" "$T/" || exit 1
distrobox enter ubuntu -- bash -c "cd '$T' && g++ -std=c++20 -O1 -Wall -Wextra -I. test_fa0439.cpp -o t && ./t; \
 for p in SKIP BREV; do g++ -std=c++20 -O1 -DBC5_FA439_PLANT_\$p -I. test_fa0439.cpp -o tp && echo \"plant \$p: \$(./tp | tail -1)\"; done"
