#!/usr/bin/env bash
# BC5 exp 0439 (tag dm439): builds and runs test_dm0439.cpp in the ubuntu distrobox against the vendored vgmstream ATRAC9
# sources of the shared tree, then once more with BC5_DM439_PLANT (the old behaviour), which must FAIL. CPU only.
set -u
H=$HOME/bc5-work/exp0439/k439; V=$HOME/src/KytyPlus/3rdparty/vgmstream-atrac9/src/coding/libs; T=$H/tdm
rm -rf "$T"; mkdir -p "$T/bc5" && cp "$H/dm0439.hpp" "$T/bc5/" && cp "$H/test_dm0439.cpp" "$T/" || exit 1
distrobox enter ubuntu -- bash -c "cd '$T' && gcc -std=c11 -O1 -c '$V/atrac9_dec.c' '$V/atrac9_internal.c' -I'$V' \
 && g++ -std=c++20 -O1 -Wall -Wextra -I. -I'$V' test_dm0439.cpp atrac9_dec.o atrac9_internal.o -lm -o t && ./t; echo \"rc \$?\"; \
 g++ -std=c++20 -O1 -DBC5_DM439_PLANT -I. -I'$V' test_dm0439.cpp atrac9_dec.o atrac9_internal.o -lm -o tp && ./tp | tail -1; echo \"plant rc \$? (must be FAIL)\""
