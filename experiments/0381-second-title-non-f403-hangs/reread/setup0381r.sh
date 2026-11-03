#!/usr/bin/env bash
# BC5 exp 0381, re-reads: on the box, under the series' lock line, claimed before this: unpack the tools sent on stdin, build and test the
# private mount, build the private emulator (test build 2's two units with the F687 and F688 catchers, linked as tb2 was), make the
# private launcher. Leaves the lock held for the arms. Shared files are read, never written.
# series0381r.sh sends this text after the lock helper, with W, TB2_TOKEN and BC5_SRC (a tar on the box) set.
E=$W/exp0381; TB=$E/tb2; RR=$E/reread; EM=$RR/emu; R1=$W/exp0380r1; B=$W/kytyplus-build; K=$HOME/src/KytyPlus
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
tb2_own
mkdir -p "$RR/src" "$RR/raw"
tar -xf "$BC5_SRC" -C "$RR/src" || { echo "the tools did not unpack"; exit 5; }
distrobox enter ubuntu -- bash -lc "cd '$RR/src/tools' && cargo build --release -p bc5-mount --target-dir '$RR/target' && cargo test -p bc5-mount --target-dir '$RR/target-test'" < /dev/null > "$RR/raw/build.txt" 2>&1 || { echo "build or test failed: $RR/raw/build.txt"; tail -5 "$RR/raw/build.txt"; exit 5; }
grep -c '^test result: ok' "$RR/raw/build.txt"
tb2_own
# The binary of RR3-RR5 is kept: since 11-03 tb2's unit no longer compiles against the shared KytyPlus sources.
if [ "$(md5sum < "$RR/bin/kyty_emulator" 2> /dev/null | cut -c1-8)" = "${BC5_0381_EMU_MD5:-be846ba2}" ]; then
    echo "emulator kept: $(md5sum < "$RR/bin/kyty_emulator" | cut -c1-8)"
else
    mkdir -p "$EM/src/libs/bc5" "$EM/src/loader" "$EM/obj" "$RR/bin"
    cp "$TB/src/libs/bc5/"* "$EM/src/libs/bc5/" && cp "$TB/src/loader/runtimeLinker.cpp" "$EM/src/loader/" || { echo "the private sources did not copy"; exit 5; }
    python3 -I "$RR/mkcatch0381r.py" "$TB/src/libs/bc5LleAgc.cpp" "$EM/src/libs/bc5LleAgc.cpp" "$RR" || { echo "the catchers' anchors do not fit test build 2's unit"; exit 5; }
    distrobox enter ubuntu -- python3 -I "$R1/build0380y.py" "$TB/compdb.json" "$B" "$EM/obj" "$RR/bin/kyty_emulator" "libs/bc5LleAgc.cpp.o=$EM/src/libs/bc5LleAgc.cpp=$K/src/libs" "loader/runtimeLinker.cpp.o=$EM/src/loader/runtimeLinker.cpp=$K/src/loader" < /dev/null > "$RR/raw/build-emu.txt" 2>&1 || { sed 's/\x1b\[[0-9;]*m//g' "$RR/raw/build-emu.txt" | grep -n 'error:\|undefined\|COMPILE FAILED' | head -20; echo "the emulator did not build"; exit 5; }
fi
[ "$(strings "$RR/bin/kyty_emulator" | grep -c '^BC5_0381_REOPEN_TRACE$')" -ge 1 ] && [ "$(strings "$RR/bin/kyty_emulator" | grep -c '^BC5_0381_PAGE_CHECK$')" -ge 1 ] || { echo "the switches are not in the binary"; exit 5; }
# The run settings of RR3-RR5, private: the shared bc5-run.env was rewritten on 11-02 for the new build, without the 17 lines
# be846ba2 needs (BC5_DIRECT_STAGE=all among them), and RT2 stalled in its first load. Taken once from RR5 W2's log, which printed them.
ENVO=$RR/run-0381.env
if [ ! -s "$ENVO" ]; then
    sed -n '/^BC5_GC_MODE=/,/^[^A-Z_]/p' "$TB/play/play-20261101-164742.log" | grep -E '^[A-Z_0-9]+=' > "$ENVO.new" && mv "$ENVO.new" "$ENVO"
fi
grep -qx 'BC5_DIRECT_STAGE=all' "$ENVO" && grep -qx 'BC5_DIRECT_RINGS=1' "$ENVO" && ! grep -q '^BC5_DIRECT_JOURNAL=' "$ENVO" || { echo "the private run settings"; exit 5; }
echo "run settings: $(grep -c . "$ENVO") lines, $(md5sum < "$ENVO" | cut -c1-8)"
# F687: every arm has the learned line of the 20:39 fault, as the next play will.
[ ! -L "$E/direct-learned-pkg.txt" ] && cp "$W/direct-learned-pkg.txt" "$E/direct-learned-pkg.txt" || { echo "the private learned file"; exit 5; }
grep -qx '0x110e000000 0x6000000' "$E/direct-learned-pkg.txt" || { echo "no learned line for the fault"; exit 5; }
sed -e 's#^BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount$#BM='"$RR"'/target/release/bc5-mount#' -e 's#BC5_MOUNT_DISK_CACHE=$HOME/bc5-data/cache/bc5-mount$#BC5_MOUNT_DISK_CACHE=${BC5_0381_DC:-$HOME/bc5-data/cache/bc5-mount}#' "$TB/play-pkg-0381tb2s.sh" > "$RR/play-pkg-0381r.sh"
chmod +x "$RR/play-pkg-0381r.sh"
[ "$(grep -c "^BM=$RR/target/release/bc5-mount\$" "$RR/play-pkg-0381r.sh")" = 1 ] || { echo "the launcher's BM line did not change"; exit 5; }
[ "$(grep -c 'BC5_MOUNT_DISK_CACHE=${BC5_0381_DC:-$HOME/bc5-data/cache/bc5-mount}$' "$RR/play-pkg-0381r.sh")" = 1 ] || { echo "the launcher's disk cache line did not change"; exit 5; }
[ "$(diff "$TB/play-pkg-0381tb2s.sh" "$RR/play-pkg-0381r.sh" | grep -c '^[<>]')" = 4 ] || { echo "the launcher differs in more than two lines"; exit 5; }
pgrep -x bc5-mount > /dev/null && { echo "a mount is still running"; exit 3; }
tb2_own
echo "set up: mount $(md5sum < "$RR/target/release/bc5-mount" | cut -c1-8), emulator $(md5sum < "$RR/bin/kyty_emulator" | cut -c1-8), shared normal $(md5sum < "$B/src/kyty_emulator" | cut -c1-8), launcher $(md5sum < "$RR/play-pkg-0381r.sh" | cut -c1-8)"
