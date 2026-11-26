#!/usr/bin/env bash
# BC5 exp 0444: build the backend of exp/0444-gpu-waits on the box, in the ubuntu distrobox. No GPU.
#   - wait-rings (BC5_WITH_AMDGPU=ON) into ~/bc5-work/exp0444/build/wait-rings
#   - the backend unit tests (GCC, warnings as errors) and their run: bc5_backend_tests
# The source is the branch's backend/ as shipped by the laptop: ~/bc5-work/exp0444/src/backend
# (tar from `git archive`, with its commit in src/COMMIT). Not the shared builds: nothing shared is
# written. Refuses while an emulator runs (a build beside a play or a timing run costs it).
# Start: systemd-run --user --unit=bc5-b444 --collect -p RuntimeMaxSec=1800 \
#        bash ~/bc5-work/exp0444/kit/build444.sh
set -u
W=$HOME/bc5-work/exp0444
S=$W/src/backend
B=$W/build
L=$W/build444.log
exec > >(tee -a "$L") 2>&1
echo "== build444 $(date '+%F %T'), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), source $(cat "$W/src/COMMIT" 2> /dev/null || echo '?')"
pgrep '^kyty_emulator' > /dev/null && { echo "REFUSED: an emulator runs"; exit 1; }
[ -f "$S/CMakeLists.txt" ] || { echo "no $S/CMakeLists.txt"; exit 1; }
distrobox enter ubuntu -- bash -c "
  set -e
  cmake -S '$S' -B '$B' -G Ninja -DCMAKE_BUILD_TYPE=Release -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON > '$W/cmake444.log' 2>&1 || { tail -20 '$W/cmake444.log'; exit 1; }
  nice -n 10 cmake --build '$B' --target wait-rings bc5_backend_tests -j 8
  '$B/bc5_backend_tests' 2>&1 | tail -3
  '$B/wait-rings' --case all > '$W/wait-rings-dry-box.txt' 2>&1; echo \"dry run rc \$?: \$(tail -1 '$W/wait-rings-dry-box.txt')\"
"
RC=$?
echo "== build444 rc $RC; wait-rings md5 $(md5sum < "$B/wait-rings" 2> /dev/null | cut -c1-8)"
exit $RC
