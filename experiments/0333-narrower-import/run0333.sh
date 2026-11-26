#!/usr/bin/env bash
# BC5 experiment 0333, phase S: exp 0333's zero map (patch0333.py) as a private binary.
#   build   patch exp 0330's bc5LleAgc.mem.cpp (md5 29664e3c) into ~/bc5-work/exp0333/src/bc5LleAgc.0333.cpp and link
#           ~/bc5-work/exp0333/kyty_emulator from the shared normal build's objects (4a146894) plus exp 0332's
#           runtimeLinker.cpp.o (the extended crash dump; build0333.py, nice 19, a fresh compdb.json from ninja). Its md5
#           goes to ~/bc5-work/exp0333/binary.md5 for s6n0333.sh. No emulator, no GPU; the shared build, its objects,
#           exps 0330/0332's files and ~/src/KytyPlus are only read.
# usage: run0333.sh build   (on the box, with patch0333.py and build0333.py in ~/bc5-work/exp0333)
set -u
E=$HOME/bc5-work/exp0333; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
IN=$HOME/bc5-work/exp0330/src/bc5LleAgc.mem.cpp; IN_MD5=29664e3cdfec8c02410fdf59f9b5c116
md5() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5sum < "$IN" | cut -c1-32)" = "$IN_MD5" ] || { echo "$IN is not 29664e3c: stop"; exit 1; }
  [ "$(md5 "$B/src/kyty_emulator")" = 4a146894 ] || { echo "the shared normal build is not 4a146894: stop"; exit 1; }
  echo "cloud exp 0333 | build of ~/bc5-work/exp0333/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0333 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "exp 0330 source $(stat -c '%y' "$IN") md5 $IN_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5 "$B/src/kyty_emulator")"
    echo "exp 0332 object $(stat -c '%y' "$HOME/bc5-work/exp0332/obj/runtimeLinker.cpp.o") md5 $(md5 "$HOME/bc5-work/exp0332/obj/runtimeLinker.cpp.o")"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0333.py" "$IN" "$E/src/bc5LleAgc.0333.cpp" "$R/patch_0333.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0333.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc" | tee -a "$R/build.out"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "bc5LleAgc.0333.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  if [ "$rc" = 0 ] && [ -x "$BIN" ]; then
    md5 "$BIN" > "$E/binary.md5"
    ls -la "$BIN"; echo "md5 $(cat "$E/binary.md5")"; echo "zero-map strings: $(strings "$BIN" | grep -c 'zero map (exp 0333)'), frame-dump strings: $(strings "$BIN" | grep -c 'frame \[\[rbp')"
  fi
  exit $rc
  ;;
*) echo "usage: run0333.sh build"; exit 2 ;;
esac
