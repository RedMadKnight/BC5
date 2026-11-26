#!/usr/bin/env bash
# BC5 experiment 0276: two KytyPlus upstream library fixes (F335) as a private binary — exp 0273's pattern for two units.
#   build   check the shared tree's audio.cpp and libAmpr.cpp md5s, copy them to ~/bc5-work/exp0276/src/, apply
#           audio.diff and libAmpr.diff there (patch --dry-run first; the tree is only read), and link
#           ~/bc5-work/exp0276/kyty_emulator from the shared normal build's other objects (build0276.py, nice 19,
#           a fresh compdb.json from ninja). No emulator, no GPU; ~/src/KytyPlus and the shared build are only read.
#   sinks   check-pad-sinks.sh (read-only): every sink's channel count and rate.
# usage: run0276.sh build | sinks   (on the box, with audio.diff, libAmpr.diff, build0276.py, check-pad-sinks.sh in ~/bc5-work/exp0276)
set -u
E=$HOME/bc5-work/exp0276; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
EXPECT_AUDIO=03b3af4e   # F330: the tree's audio.cpp after exp 0267's integration
EXPECT_AMPR=5f2ec30b    # patch 0001 at c8a38cc applied to f266548 (LF), measured on the laptop
EXPECT_SHARED=7947154c  # the shared normal binary after exp 0278's integration (top session, 22:06)
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  echo "ports exp 0276 | build of ~/bc5-work/exp0276/kyty_emulator (two units + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
  trap 'grep -q "^ports exp 0276 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  a=$(md5sum < "$K/src/libs/audio.cpp" | cut -c1-8); m=$(md5sum < "$K/src/libs/libAmpr.cpp" | cut -c1-8); s=$(md5sum < "$B/src/kyty_emulator" | cut -c1-8)
  { echo "tree src/libs/audio.cpp md5 $a (expect $EXPECT_AUDIO) $(stat -c '%y' "$K/src/libs/audio.cpp")"
    echo "tree src/libs/libAmpr.cpp md5 $m (expect $EXPECT_AMPR) $(stat -c '%y' "$K/src/libs/libAmpr.cpp")"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $s (expect $EXPECT_SHARED)"; } | tee "$R/build-inputs.txt"
  [ "$a" = "$EXPECT_AUDIO" ] && [ "$m" = "$EXPECT_AMPR" ] && [ "$s" = "$EXPECT_SHARED" ] || { echo "md5 mismatch: stop"; exit 1; }
  cp "$K/src/libs/audio.cpp" "$K/src/libs/libAmpr.cpp" "$E/src/"
  # The box has no patch(1); git apply outside a repository applies to paths relative to the cwd.
  for f in audio libAmpr; do
    ( cd "$E/src" && git apply --check -p3 -v "$E/$f.diff" ) > "$R/patch-$f.out" 2>&1 || { echo "$f.diff does not apply:"; cat "$R/patch-$f.out"; exit 1; }
    ( cd "$E/src" && git apply -p3 -v "$E/$f.diff" ) >> "$R/patch-$f.out" 2>&1 || exit 1
  done
  { cd "$E/src" && for f in audio libAmpr; do diff -u "$K/src/libs/$f.cpp" "$f.cpp" | sed "s#^--- .*#--- a/src/libs/$f.cpp#; s#^+++ .*#+++ b/src/libs/$f.cpp#"; done; } > "$R/patch_0276.diff"
  echo "patched: audio.cpp $(md5sum < "$E/src/audio.cpp" | cut -c1-8) libAmpr.cpp $(md5sum < "$E/src/libAmpr.cpp" | cut -c1-8)" | tee -a "$R/build-inputs.txt"
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0276.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "exp0276/src/[A-Za-z0-9]*\.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -40
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "private md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "new strings: $(strings "$BIN" | grep -c "Wireless Controller")"; }
  echo "shared binary after: $(md5sum < "$B/src/kyty_emulator" | cut -c1-8) (expect $EXPECT_SHARED)" | tee -a "$R/build-inputs.txt"
  exit $rc
  ;;
sinks)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  bash "$E/check-pad-sinks.sh" | tee "$R/sinks.txt"
  ;;
*) echo "usage: run0276.sh build | sinks"; exit 2 ;;
esac
