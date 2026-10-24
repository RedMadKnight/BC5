#!/usr/bin/env bash
# BC5 experiment 0281: exp 0277's breadcrumbs on the shared tree after exp 0278's integration (patch0281.py), as a
# private binary for RT-off catch runs.
#   build     patch the tree's bc5LleAgc.cpp (md5 5bccbb80) into ~/bc5-work/exp0281/src/bc5LleAgc.bc.cpp and link
#             ~/bc5-work/exp0281/kyty_emulator from the shared normal build's objects (build0281.py, nice 19, a fresh
#             compdb.json from ninja). No emulator, no GPU; the shared build, its objects and ~/src/KytyPlus are only
#             read.
#   launcher  print the lines a play wrapper adds for an RT-off catch run with breadcrumbs; nothing is written.
# usage: run0281.sh build | launcher   (on the box, with patch0281.py, patch0277.py and build0281.py in ~/bc5-work/exp0281)
set -u
E=$HOME/bc5-work/exp0281; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
TREE_MD5=5bccbb808c397f3180330425917b04c6
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$K/src/libs/bc5LleAgc.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80: stop"; exit 1; }
  echo "tcp exp 0281 | build of ~/bc5-work/exp0281/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^tcp exp 0281 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$K/src/libs/bc5LleAgc.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"
    echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0281.py" "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.bc.cpp" "$R/patch_0281.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }  # -x: the @rsp files inlined (ninja deletes them)
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0281.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc" | tee -a "$R/build.out"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.bc.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "breadcrumb strings: $(strings "$BIN" | grep -c "exp 0277"); switch strings: $(strings "$BIN" | grep -c "ray tracing")"; }
  exit $rc
  ;;
launcher)
  cat <<'L'
# experiment 0281: RT off from the start (exp 0278, integrated; the launchers carry exp 0280 arm A's build list) with
# breadcrumbs (exp 0277, level 1: reached and done marks). The title's saved RayTracing.<TITLE_ID> overrides KYTY_BC5_RT.
export KYTY_BC5_RT=0
export BC5_DIRECT_BREADCRUMBS=1
L
  ;;
*) echo "usage: run0281.sh build | launcher"; exit 2 ;;
esac
