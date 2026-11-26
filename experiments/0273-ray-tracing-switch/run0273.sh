#!/usr/bin/env bash
# BC5 experiment 0273: the ray-tracing switch (patch0273.py), as a private binary — exp 0272's pattern for three units.
#   build   patch the shared tree's bc5LleAgc.cpp, hostMenu.cpp and hostInput.cpp into ~/bc5-work/exp0273/src/ and link
#           ~/bc5-work/exp0273/kyty_emulator from the shared normal build's other objects (build0273.py, nice 19, a fresh
#           compdb.json from ninja). No emulator, no GPU; the shared build, its objects and ~/src/KytyPlus are only read.
#   launcher  print the two lines play-pkg.sh needs (the build list and the default); nothing is written.
# usage: run0273.sh build | launcher   (on the box, with patch0273.py and build0273.py in ~/bc5-work/exp0273)
set -u
E=$HOME/bc5-work/exp0273; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  echo "bvh exp 0273 | build of ~/bc5-work/exp0273/kyty_emulator (three units + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
  trap 'grep -q "^bvh exp 0273 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { for f in src/libs/bc5LleAgc.cpp src/graphics/presentation/hostMenu.cpp src/graphics/presentation/window/hostInput.cpp; do
      echo "tree $f $(stat -c '%y' "$K/$f") md5 $(md5sum < "$K/$f" | cut -c1-8)"; done
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5sum < "$B/src/kyty_emulator" | cut -c1-8)"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0273.py" "$K" "$E/src" || exit 1   # refuses on any anchor mismatch; writes $E/src/patch_0273.diff
  cp "$E/src/patch_0273.diff" "$R/patch_0273.diff"
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0273.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "exp0273/src/[A-Za-z0-9]*\.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -40
  [ -x "$BIN" ] && { ls -la "$BIN"; echo "md5 $(md5sum < "$BIN" | cut -c1-8)"; echo "switch strings: $(strings "$BIN" | grep -c "ray tracing")"; }
  exit $rc
  ;;
launcher)
  cat <<'L'
# experiment 0273: the programs dropped with the window's Ray tracing switch off (Emulation menu; KYTY_BC5_RT=0 starts it
# off): the BVH compaction and the "Ray Tracing Update" chain (F332, F234); the traversals are found by their code.
export KYTY_BC5_RT_BUILD_PGM=${KYTY_BC5_RT_BUILD_PGM:-909974400,909939400,909936c00,909939700,909939900}
L
  ;;
*) echo "usage: run0273.sh build | launcher"; exit 2 ;;
esac
