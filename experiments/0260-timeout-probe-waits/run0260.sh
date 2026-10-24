#!/usr/bin/env bash
# BC5 experiment 0260: the timeout probe that catches a stuck compute buffer (patch0260.py), as a private binary.
#   build   patch the shared tree's bc5LleAgc.cpp (md5 67859271) into ~/bc5-work/exp0260/src/bc5LleAgc.probe.cpp and
#           link ~/bc5-work/exp0260/kyty_emulator from the shared normal build's objects (build0260.py, nice 19, a fresh
#           compdb.json from ninja). No emulator, no GPU; the shared build, its objects and ~/src/KytyPlus are only read.
# usage: run0260.sh build   (on the box, with patch0260.py and build0260.py in ~/bc5-work/exp0260)
set -u
E=$HOME/bc5-work/exp0260; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
TREE_MD5=67859271bf3ec04c6c2bac20e034688e
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$K/src/libs/bc5LleAgc.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's bc5LleAgc.cpp is not 67859271: stop"; exit 1; }
  echo "tcp exp 0260 | build of ~/bc5-work/exp0260/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^tcp exp 0260 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$K/src/libs/bc5LleAgc.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"
    echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0260.py" "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.probe.cpp" "$R/patch_0260.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }  # -x: the @rsp files inlined (ninja deletes them)
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0260.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.probe.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "probe strings: $(strings "$BIN" | grep -c "timeout probe: wait op\|timeout probe: write op\|timeout probe: dispatch op")"; }
  exit $rc
  ;;
*) echo "usage: run0260.sh build"; exit 2 ;;
esac
