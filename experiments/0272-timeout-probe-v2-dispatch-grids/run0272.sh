#!/usr/bin/env bash
# BC5 experiment 0272: probe v2, the dispatch grids (patch0272.py), as a private binary for a compile check.
#   build   patch the shared tree's bc5LleAgc.cpp (md5 daca24cc) into ~/bc5-work/exp0272/src/bc5LleAgc.v2.cpp and
#           link ~/bc5-work/exp0272/kyty_emulator from the shared normal build's objects (build0272.py, nice 19, a fresh
#           compdb.json from ninja). No emulator, no GPU; the shared build, its objects and ~/src/KytyPlus are only read.
# usage: run0272.sh build   (on the box, with patch0272.py and build0272.py in ~/bc5-work/exp0272)
set -u
E=$HOME/bc5-work/exp0272; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
TREE_MD5=daca24cca83fa6e8ec1778b3422470db
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$K/src/libs/bc5LleAgc.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's bc5LleAgc.cpp is not daca24cc: stop"; exit 1; }
  echo "tcp exp 0272 | build of ~/bc5-work/exp0272/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^tcp exp 0272 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$K/src/libs/bc5LleAgc.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"
    echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0272.py" "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.v2.cpp" "$R/patch_0272.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }  # -x: the @rsp files inlined (ninja deletes them)
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0272.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.v2.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "v2 count-line format: $(strings "$BIN" | grep -c "the largest grid")"; }
  exit $rc
  ;;
*) echo "usage: run0272.sh build"; exit 2 ;;
esac
