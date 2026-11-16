#!/bin/bash
# BC5 exp 0428 step 2: the CP's indirect-count check around REAL compute-form DISPATCH_INDIRECTs on compute rings 0..2
# (userdata-rings --cp-check), once. Builds the tool from ~/bc5-work/exp0428/tool/backend (copied there by the laptop),
# runs its dry run, then the GPU test; dmesg before and after. One BOX-LOCK line through box0428.sh (claim/release).
# usage (on the box, in ~/bc5-work/exp0428): bash cp0428.sh
set -u
E=$HOME/bc5-work/exp0428; T=$E/tool; R=$E/raw
cd "$E" || exit 1
pgrep '^kyty_emulator' > /dev/null && { echo "STOP: an emulator runs"; exit 1; }
[ -e "$R/cp-run.txt" ] && { echo "STOP: $R/cp-run.txt exists, the test ran already"; exit 1; }
bash box0428.sh claim "exp 0428 step 2: build userdata-rings + ONE --cp-check (18 real DISPATCH_INDIRECTs under the CP check, compute rings 0..2)" 20 || exit 1
trap 'bash "$E/box0428.sh" release' EXIT
mkdir -p "$R"
distrobox enter ubuntu -- bash -c "cd $T && nice -n 10 cmake -S backend -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF > configure.log 2>&1 && nice -n 10 cmake --build build --target userdata-rings -j4 > build.log 2>&1; echo build-exit \$?; grep -c 'warning:' build.log" < /dev/null
[ -x "$T/build/userdata-rings" ] || { echo "STOP: no binary"; exit 1; }
sha256sum "$T/build/userdata-rings" | tee "$R/cp-tool.sha256"
"$T/build/userdata-rings" --cp-dry < /dev/null > "$R/cp-dry.txt" 2>&1 || { tail -3 "$R/cp-dry.txt"; echo "STOP: the dry run failed"; exit 1; }
tail -1 "$R/cp-dry.txt"
pgrep '^kyty_emulator' > /dev/null && { echo "STOP: an emulator appeared"; exit 1; }
sudo -n dmesg < /dev/null > "$R/cp-dmesg-before.txt" 2>&1
echo "== cp-check at $(LC_ALL=C date '+%F %T.%N')"
distrobox enter ubuntu -- bash -c "cd $T && timeout 120 ./build/userdata-rings --cp-check" < /dev/null > "$R/cp-run.txt" 2>&1
echo "cp-exit $?"
sleep 2
sudo -n dmesg < /dev/null > "$R/cp-dmesg-after.txt" 2>&1
echo "== new dmesg lines: $(diff "$R/cp-dmesg-before.txt" "$R/cp-dmesg-after.txt" | grep -c '^>')"
diff "$R/cp-dmesg-before.txt" "$R/cp-dmesg-after.txt" | grep '^>' | tail -20
cat "$R/cp-run.txt"
