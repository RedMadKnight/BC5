#!/usr/bin/env bash
# BC5 experiment 0277: breadcrumbs (patch0277.py), as a private binary.
#   build   patch the shared tree's bc5LleAgc.cpp (md5 a2a2c2df) into ~/bc5-work/exp0277/src/bc5LleAgc.bc.cpp and
#           link ~/bc5-work/exp0277/kyty_emulator from the shared normal build's objects (build0277.py, nice 19, a fresh
#           compdb.json from ninja). Also records, for the packets' TODO(verify)s, Mesa sid.h's COPY_DATA and RELEASE_MEM
#           field defines (~/src/mesa, read only) and udmabuf's size limit (the slot buffer is 32 MiB + 4 KiB).
#           No emulator, no GPU; the shared build, its objects and ~/src/KytyPlus are only read.
# usage: run0277.sh build   (on the box, with patch0277.py and build0277.py in ~/bc5-work/exp0277)
set -u
E=$HOME/bc5-work/exp0277; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator; M=$HOME/src/mesa
TREE_MD5=a2a2c2df5e7017eee69d6b12f374e099
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$K/src/libs/bc5LleAgc.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's bc5LleAgc.cpp is not a2a2c2df: stop"; exit 1; }
  echo "tcp exp 0277 | build of ~/bc5-work/exp0277/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^tcp exp 0277 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$K/src/libs/bc5LleAgc.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"
    echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
  { echo "mesa $(git -C "$M" log -1 --format='%h %ci' 2> /dev/null || echo '(no git)')"
    grep -n "COPY_DATA_SRC_SEL\|COPY_DATA_SRC_MEM\|COPY_DATA_DST_SEL\|COPY_DATA_DST_MEM\b\|COPY_DATA_COUNT_SEL\|COPY_DATA_WR_CONFIRM\|PKT3_COPY_DATA\b\|PKT3_RELEASE_MEM\b\|S_490_EVENT_TYPE\|S_490_EVENT_INDEX\|S_030358_DATA_SEL\|S_030358_DST_SEL\|EOP_DATA_SEL_VALUE_32BIT" "$M/src/amd/common/sid.h" 2>&1
    echo "udmabuf size_limit_mb $(cat /sys/module/udmabuf/parameters/size_limit_mb 2>&1)"; } > "$R/packet-fields.txt"
  cat "$R/packet-fields.txt"
  python3 -I "$E/patch0277.py" "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.bc.cpp" "$R/patch_0277.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }  # -x: the @rsp files inlined (ninja deletes them)
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0277.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.bc.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "breadcrumb strings: $(strings "$BIN" | grep -c "exp 0277")"; }
  exit $rc
  ;;
*) echo "usage: run0277.sh build"; exit 2 ;;
esac
