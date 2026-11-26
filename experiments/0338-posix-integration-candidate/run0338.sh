#!/usr/bin/env bash
# BC5 experiment 0338: the integration candidate (patch0338.py: exp 0336's fixes and the posix NIDs on the posix entry
# points) as two private binaries, before any change to the shared builds (D19).
#   build   patch the tree's five files (md5-checked by patch0338.py) into ~/bc5-work/exp0338/src and link
#           ~/bc5-work/exp0338/kyty_emulator from the shared normal build's objects (4a146894) and
#           ~/bc5-work/exp0338/lean/kyty_emulator from the shared lean build's (c28cdd3c) (build0338.py, nice 19, a fresh
#           compdb.json from each build's ninja); the md5s go to binary.md5 and lean/binary.md5. No emulator, no GPU; the
#           shared builds, their objects and ~/src/KytyPlus are only read.
# usage: run0338.sh build   (on the box, with patch0338.py and build0338.py in ~/bc5-work/exp0338)
set -u
E=$HOME/bc5-work/exp0338; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BL=$HOME/bc5-work/kytyplus-build-lean
md5() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$R" "$E/src" "$E/lean"
case "${1:-}" in
build)
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5 "$B/src/kyty_emulator")" = 4a146894 ] || { echo "the shared normal build is not 4a146894: stop"; exit 1; }
  [ "$(md5 "$BL/src/kyty_emulator")" = c28cdd3c ] || { echo "the shared lean build is not c28cdd3c: stop"; exit 1; }
  echo "cloud exp 0338 | build of ~/bc5-work/exp0338/kyty_emulator and lean/kyty_emulator (four units + link each, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +20min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0338 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  {
    echo "shared normal $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5 "$B/src/kyty_emulator")"
    echo "shared lean   $(stat -c '%y %s' "$BL/src/kyty_emulator") md5 $(md5 "$BL/src/kyty_emulator")"
  } > "$R/build-inputs.txt"
  python3 -I "$E/patch0338.py" "$K/src" "$E/src" "$R/patch_0338.diff" | tee -a "$R/build-inputs.txt"
  [ "${PIPESTATUS[0]}" = 0 ] || exit 1
  rc=0
  for v in normal lean; do
    bd=$B; out=$E; [ $v = lean ] && { bd=$BL; out=$E/lean; }
    echo "== $(date +%T) $v compdb"
    distrobox enter ubuntu -- sh -c "cd '$bd' && ninja -t compdb -x" > "$out/compdb.json" 2> "$R/compdb-$v.err" || { echo "compdb failed"; exit 1; }
    grep -q '"command": "[^"]* @' "$out/compdb.json" && { echo "the compdb still names response files"; exit 1; }
    grep -q '"output": "src/kyty_emulator"' "$out/compdb.json" || { echo "no link command in the compdb"; exit 1; }
    echo "== $(date +%T) $v build"
    ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0338.py" "$out/compdb.json" $v ) > "$R/build-$v.out" 2>&1
    r=$?
    echo "== $(date +%T) $v build rc $r" | tee -a "$R/build-$v.out"
    echo "warnings: $(grep -c "warning:" "$R/build-$v.out")"
    grep -A3 "exp0338/src/.*:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build-$v.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -40
    if [ "$r" = 0 ] && [ -x "$out/kyty_emulator" ]; then
      md5 "$out/kyty_emulator" > "$out/binary.md5"
      ls -la "$out/kyty_emulator"; echo "$v md5 $(cat "$out/binary.md5")"
      echo "strings: $(strings "$out/kyty_emulator" | grep -c 'BC5_IMPORT_LOG\|Posix::sched_yield\|Posix::pthread_cond_destroy')"
    else
      rc=1
    fi
  done
  exit $rc
  ;;
*) echo "usage: run0338.sh build"; exit 2 ;;
esac
