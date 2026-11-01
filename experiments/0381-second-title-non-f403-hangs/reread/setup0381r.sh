#!/usr/bin/env bash
# BC5 exp 0381, re-reads: on the box, under a new claim of the series' lock line: unpack the tools sent on stdin, build and test the
# private mount, make the private launcher. Leaves the lock held for the arms. Shared files are read, never written.
# series0381r.sh sends this text after the lock helper, with W, TB2_TOKEN and BC5_SRC (a tar on the box) set.
E=$W/exp0381; TB=$E/tb2; RR=$E/reread
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
trap tb2_held_release EXIT
tb2_claim
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
tb2_queue "$TB2_LINE: mount reread series | $(date '+%F %T')"
mkdir -p "$RR/src" "$RR/raw"
tar -xf "$BC5_SRC" -C "$RR/src" || { echo "the tools did not unpack"; exit 5; }
distrobox enter ubuntu -- bash -lc "cd '$RR/src/tools' && cargo build --release -p bc5-mount --target-dir '$RR/target' && cargo test -p bc5-mount --target-dir '$RR/target-test'" > "$RR/raw/build.txt" 2>&1 || { echo "build or test failed: $RR/raw/build.txt"; tail -5 "$RR/raw/build.txt"; exit 5; }
grep -c '^test result: ok' "$RR/raw/build.txt"
sed -e 's#^BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount$#BM='"$RR"'/target/release/bc5-mount#' "$TB/play-pkg-0381tb2s.sh" > "$RR/play-pkg-0381r.sh"
chmod +x "$RR/play-pkg-0381r.sh"
[ "$(grep -c "^BM=$RR/target/release/bc5-mount\$" "$RR/play-pkg-0381r.sh")" = 1 ] || { echo "the launcher's BM line did not change"; exit 5; }
[ "$(diff "$TB/play-pkg-0381tb2s.sh" "$RR/play-pkg-0381r.sh" | grep -c '^[<>]')" = 2 ] || { echo "the launcher differs in more than one line"; exit 5; }
pgrep -x bc5-mount > /dev/null && { echo "a mount is still running"; exit 3; }
tb2_own
TB2_HELD=0
echo "set up: mount $(md5sum < "$RR/target/release/bc5-mount" | cut -c1-8), launcher $(md5sum < "$RR/play-pkg-0381r.sh" | cut -c1-8)"
