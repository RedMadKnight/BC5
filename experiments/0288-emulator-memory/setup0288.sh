#!/usr/bin/env bash
# BC5 experiment 0288, box side, in the granted slot (exp 0252's setup0252.sh with the unit changed): the private build
# with BC5_DIRECT_BREAKDOWN_AT. Copies the shared tree's src/libs/bc5LleAgc.cpp (read-only), applies patch0288.py,
# takes the shared build's compile database and runs build0288.py in the ubuntu distrobox. Writes only under
# ~/bc5-work/exp0288; holds one BOX-LOCK line meanwhile. CPU only, nice 19; no emulator is started.
set -e
cd ~/bc5-work
pgrep '^kyty_emulator' > /dev/null && { echo "emulator running: stop"; exit 1; }
[ -s BOX-LOCK ] && { echo "locked: $(cat BOX-LOCK)"; exit 1; }
echo "exp 0288 | private build of bc5LleAgc.cpp (BREAKDOWN_AT), no emulator | start $(date +%H:%M) | until ~$(date -d '+8 min' +%H:%M)" > BOX-LOCK
trap 'grep -q "exp 0288 | private build" BOX-LOCK 2> /dev/null && rm -f BOX-LOCK' EXIT
E=~/bc5-work/exp0288
mkdir -p "$E/src" "$E/raw"
md5sum ~/src/KytyPlus/src/libs/bc5LleAgc.cpp ~/bc5-work/kytyplus-build/src/kyty_emulator | tee "$E/raw/build-inputs.txt"
cp ~/src/KytyPlus/src/libs/bc5LleAgc.cpp "$E/src/bc5LleAgc.shared.cpp"
python3 -I "$E/patch0288.py" "$E/src/bc5LleAgc.shared.cpp" "$E/src/bc5LleAgc.0288.cpp" | tee -a "$E/raw/build-inputs.txt"
diff -u "$E/src/bc5LleAgc.shared.cpp" "$E/src/bc5LleAgc.0288.cpp" > "$E/raw/patch_0288.diff" || true
distrobox enter ubuntu -- sh -c "cd ~/bc5-work/kytyplus-build && ninja -t compdb -x > $E/compdb.json"
distrobox enter ubuntu -- python3 -I "$E/build0288.py" "$E/compdb.json" 2>&1 | tee "$E/raw/build.out" | grep -v "^+ " || true
ls -la "$E/kyty_emulator" ~/bc5-work/kytyplus-build/src/kyty_emulator | tee -a "$E/raw/build-inputs.txt"
md5sum "$E/kyty_emulator" ~/bc5-work/kytyplus-build/src/kyty_emulator | tee -a "$E/raw/build-inputs.txt"
