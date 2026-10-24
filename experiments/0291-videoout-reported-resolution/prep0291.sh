#!/usr/bin/env bash
# BC5 experiment 0291: on the top session's GRANTED, make the test binary (CPU only, no GPU):
#   1. copy the shared tree's videoOut.cpp, apply patch_0291's change with apply0291.py (line endings kept), and write
#      the exact patch_0291.diff against the tree (checked with git apply --check, the tree is not written);
#   2. regenerate the normal shared build's compile database and build ~/bc5-work/exp0291/bin/kyty_emulator from the
#      shared objects plus the one changed file (build0291.py). The shared builds are not written.
# It refuses while any emulator runs or another session holds ~/bc5-work/BOX-LOCK, and holds its own lock line.
# usage: prep0291.sh   (on the box, from an attended SSH session)
set -u
E=$HOME/bc5-work/exp0291; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
F=src/graphics/presentation/videoOut.cpp
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
echo "exp 0291 | test-binary build (one file + link, no GPU; GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d '+5 min' +%H:%M)" > "$LOCK"
release() { grep -q "^exp 0291 | test-binary build" "$LOCK" 2> /dev/null && rm -f "$LOCK" && echo "BOX-LOCK released $(date +%T)"; }
mkdir -p "$E/src" "$R"
cd "$E" || { release; exit 1; }
[ "$K/$F" -ot "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" ] || { echo "the tree's videoOut.cpp is newer than the shared build: stop"; release; exit 1; }
cp -p "$K/$F" src/videoOut.base.cpp
python3 -I apply0291.py src/videoOut.base.cpp src/videoOut.cpp || { release; exit 1; }
diff -u --label "a/$F" --label "b/$F" src/videoOut.base.cpp src/videoOut.cpp > patch_0291.diff
git -C "$K" apply --check "$E/patch_0291.diff" && echo "patch_0291.diff applies to the tree (not applied)" || { echo "patch_0291.diff does not apply: stop"; release; exit 1; }
diff <(tr -d '\r' < patch_0291.diff | grep '^[-+][^-+]') <(grep '^[-+][^-+]' patch_0291-lf.diff) > /dev/null \
  && echo "its changed lines equal patch_0291-lf.diff's" || echo "WARNING: the changed lines differ from patch_0291-lf.diff"
distrobox enter ubuntu -- sh -c 'cd ~/bc5-work/kytyplus-build && ninja -t compdb' > compdb.json 2> "$R/compdb.err"
distrobox enter ubuntu -- python3 -I build0291.py compdb.json > "$R/build.txt" 2>&1
RC=$?
release
echo "build rc $RC"
sed 's/\x1b\[[0-9;]*m//g' "$R/build.txt" | grep -E "warning:|error:" | grep videoOut | cut -c1-200
ls -la --time-style=+%F_%T bin/kyty_emulator 2> /dev/null | awk '{print $6, $7}'
md5sum bin/kyty_emulator "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" 2> /dev/null
echo "switch string in the binary: $(strings bin/kyty_emulator 2> /dev/null | grep -c "KYTY_BC5_VIDEOOUT_REPORT")"
