#!/usr/bin/env bash
# BC5 experiment 0252, box side, in the granted slot: the private build of the tiler scratch pool. Copies the shared
# tree's tiler.cpp (read-only), applies patch_0252.py, takes the shared build's compile database and runs
# build0252.py in the ubuntu distrobox. Writes only under ~/bc5-work/exp0252; holds one BOX-LOCK line meanwhile.
set -e
cd ~/bc5-work
pgrep '^kyty_emulator' >/dev/null && { echo "emulator running: stop"; exit 1; }
[ -s BOX-LOCK ] && { echo "locked: $(cat BOX-LOCK)"; exit 1; }
echo "second-title-why-the-bvh exp 0252 | private build of tiler.cpp (granted) | start $(date +%H:%M) | until ~+10min" > BOX-LOCK
trap 'grep -q "exp 0252 | private build" BOX-LOCK 2>/dev/null && rm -f BOX-LOCK' EXIT
E=~/bc5-work/exp0252
mkdir -p $E/src
cp ~/src/KytyPlus/src/graphics/host_gpu/renderer/image/tiler.cpp $E/src/tiler.shared.cpp
python3 -I $E/patch_0252.py $E/src/tiler.shared.cpp $E/src/tiler.0252.cpp
distrobox enter ubuntu -- sh -c "cd ~/bc5-work/kytyplus-build && ninja -t compdb -x > $E/compdb.json"
distrobox enter ubuntu -- python3 -I $E/build0252.py $E/compdb.json
ls -la $E/kyty_emulator ~/bc5-work/kytyplus-build/src/kyty_emulator
