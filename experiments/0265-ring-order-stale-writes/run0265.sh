#!/usr/bin/env bash
# BC5 experiment 0265: the ring order's stale pending writes (patch0265.py), as a private binary. No runs here yet.
#   build   patch exp 0260's ~/bc5-work/exp0260/src/bc5LleAgc.probe.cpp (md5 daca24cc) into
#           ~/bc5-work/exp0265/src/bc5LleAgc.stale.cpp and link ~/bc5-work/exp0265/kyty_emulator from the shared normal
#           build's objects as they are at build time (a fresh ninja -t compdb -x; build0265.py, nice 19). The tree's
#           bc5LleAgc.cpp must still be 67859271, the file exp 0260's probe was made from; other units (e.g. the box
#           supervisor's SaveData fix of 2026-10-24, libSaveData.cpp.o) come in as the shared build has them and are
#           recorded. No emulator, no GPU; the shared build, its objects, ~/src/KytyPlus and exp 0260 are only read.
# usage: run0265.sh build   (on the box, with patch0265.py and build0265.py in ~/bc5-work/exp0265)
set -u
E=$HOME/bc5-work/exp0265; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
P=$HOME/bc5-work/exp0260/src/bc5LleAgc.probe.cpp; DB=$E/compdb.json; BIN=$E/kyty_emulator
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; TREE_MD5=67859271bf3ec04c6c2bac20e034688e
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$K/src/libs/bc5LleAgc.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's bc5LleAgc.cpp is not 67859271 (exp 0260's base): stop"; exit 1; }
  echo "tcp exp 0265 | build of ~/bc5-work/exp0265/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
  trap 'grep -q "^tcp exp 0265 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$K/src/libs/bc5LleAgc.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"
    echo "newest shared objects:"; find "$B/src" -name '*.o' -newer "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o" -printf '  %TY-%Tm-%Td %TH:%TM %p\n' | sort | tail -8
    echo "libSaveData object: $(find "$B/src" -name 'libSaveData.cpp.o' -printf '%TY-%Tm-%Td %TH:%TM %p')"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0265.py" "$P" "$E/src/bc5LleAgc.stale.cpp" "$R/patch_0265.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$DB" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }  # -x: the @rsp files inlined
  grep -q '"output": "src/kyty_emulator"' "$DB" || { echo "no link command in the compdb"; exit 1; }
  grep -q '"command": "[^"]* @' "$DB" && { echo "the compdb still names response files"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0265.py" "$DB" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.stale.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "stale strings: $(strings "$BIN" | grep -c "ring order: STALE pending write")"; }
  exit $rc
  ;;
*) echo "usage: run0265.sh build"; exit 2 ;;
esac
