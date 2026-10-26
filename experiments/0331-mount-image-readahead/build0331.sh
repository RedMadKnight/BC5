#!/usr/bin/env bash
# BC5 experiment 0331: the private bc5-mount (readahead off for the image and the disk cache's data file), built as
# tools/scripts/bc5-build.sh builds the shared one, from ~/bc5-work/exp0331/src/tools (BC5 main fda1c01's tools/, put
# there by the cloud session) into ~/bc5-work/exp0331/target, then copied to ~/bc5-work/exp0331/bc5-mount. The test
# launcher ~/bc5-work/exp0330/play-pkg-0330t.sh gets the new mount through its one BM= line; the shared mount, the
# shared launchers and the shortcuts are not written.
# Guards: no emulator or launcher, an empty lock, the test launcher's md5 and its BM line once. A lock line with an EXIT
# trap that clears only that line. The build is CPU only, at nice 19, offline (the crates are in ~/.cargo).
# usage: build0331.sh   (on the box)
set -u
W=$HOME/bc5-work; E=$W/exp0331; R=$E/raw; LOCK=$W/BOX-LOCK; L=$W/exp0330/play-pkg-0330t.sh
OLD_BM='BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount'
NEW_BM='BM=~/bc5-work/exp0331/bc5-mount  # exp 0331: the private bc5-mount, readahead off for the image and its disk cache'
md5() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/(play-pkg[^ ]*|test0330p)\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
pgrep -x bc5-mount > /dev/null && { echo "a bc5-mount runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -f "$E/src/tools/Cargo.lock" ] && [ -f "$E/src/tools/bc5-mount/src/io.rs" ] || { echo "no source tree in $E/src/tools: stop"; exit 1; }
grep -q 'advise_readahead_off' "$E/src/tools/bc5-mount/src/io.rs" || { echo "the source lacks the change: stop"; exit 1; }
[ "$(md5 "$L")" = bf4f3da3 ] || { echo "$L is not bf4f3da3: stop"; exit 1; }
[ "$(grep -cxF -- "$OLD_BM" "$L")" = 1 ] || { echo "the BM line is not there once: stop"; exit 1; }
[ -e "$E/bc5-mount" ] && { echo "$E/bc5-mount exists: stop"; exit 1; }
echo "cloud exp 0331 | build of the private bc5-mount (cargo, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0331 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$R" || exit 1
echo "== $(date +%T) cargo build"
distrobox enter ubuntu -- sh -c "cd '$E/src/tools' && rustc --version && cargo --version && CARGO_TARGET_DIR='$E/target' nice -n 19 cargo build --release --locked --offline -p bc5-mount" > "$R/build.out" 2>&1
rc=$?
echo "== $(date +%T) build rc $rc"; tail -n 3 "$R/build.out"
[ "$rc" = 0 ] && [ -x "$E/target/release/bc5-mount" ] || exit 1
cp -p "$E/target/release/bc5-mount" "$E/bc5-mount" || exit 1
echo "private bc5-mount $(md5 "$E/bc5-mount") ($(stat -c %s "$E/bc5-mount") B); shared $(md5 "$W/bc5-tools-ubuntu/release/bc5-mount")"
distrobox enter ubuntu -- "$E/bc5-mount" --help > /dev/null 2>&1 && echo "the private bc5-mount runs in the distrobox (--help)" || { echo "the private bc5-mount does not run"; exit 1; }
cp -p "$L" "$E/play-pkg-0330t.sh.before-0331" || exit 1
awk -v o="$OLD_BM" -v n="$NEW_BM" '$0 == o {print n; next} {print}' "$E/play-pkg-0330t.sh.before-0331" > "$L.new" && cat "$L.new" > "$L" && rm -f "$L.new" || { cat "$E/play-pkg-0330t.sh.before-0331" > "$L"; echo "RESTORED"; exit 1; }
bash -n "$L" || { cat "$E/play-pkg-0330t.sh.before-0331" > "$L"; echo "does not parse: RESTORED"; exit 1; }
diff -u "$E/play-pkg-0330t.sh.before-0331" "$L" > "$R/play-pkg-0330t-bm.diff"
[ "$(grep -c '^+[^+]' "$R/play-pkg-0330t-bm.diff")" = 1 ] && [ "$(grep -c '^-[^-]' "$R/play-pkg-0330t-bm.diff")" = 1 ] || { cat "$E/play-pkg-0330t.sh.before-0331" > "$L"; echo "not one line: RESTORED"; exit 1; }
echo "test launcher $L: bf4f3da3 -> $(md5 "$L") (BM -> $E/bc5-mount)"
echo "undo: cat $E/play-pkg-0330t.sh.before-0331 > $L"
