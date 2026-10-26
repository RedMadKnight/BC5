#!/usr/bin/env bash
# BC5 experiment 0337: patch0337.py's system language setting, as a private binary.
#   build   patch the tree's four files (one header, three units; md5-checked by patch0337.py) into ~/bc5-work/exp0337/src and link
#           ~/bc5-work/exp0337/kyty_emulator from the shared normal build's objects (4a146894; build0337.py, nice 19, a
#           fresh compdb.json from ninja); its md5 goes to ~/bc5-work/exp0337/binary.md5. No emulator, no GPU; the shared
#           build, its objects and ~/src/KytyPlus are only read.
# usage: run0337.sh build   (on the box, with patch0337.py and build0337.py in ~/bc5-work/exp0337)
set -u
E=$HOME/bc5-work/exp0337; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
md5() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$R" "$E/src"
case "${1:-}" in
build)
  pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
  [ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
  [ "$(md5 "$B/src/kyty_emulator")" = 4a146894 ] || { echo "the shared normal build is not 4a146894: stop"; exit 1; }
  echo "cloud exp 0337 | build of ~/bc5-work/exp0337/kyty_emulator (three units + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0337 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5 "$B/src/kyty_emulator")" > "$R/build-inputs.txt"
  python3 -I "$E/patch0337.py" "$K/src" "$E/src" "$R/patch_0337.diff" | tee -a "$R/build-inputs.txt" || exit 1
  [ "${PIPESTATUS[0]}" = 0 ] || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
  grep -q '"command": "[^"]* @' "$E/compdb.json" && { echo "the compdb still names response files"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0337.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc" | tee -a "$R/build.out"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "exp0337/src/.*:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -40
  if [ "$rc" = 0 ] && [ -x "$BIN" ]; then
    md5 "$BIN" > "$E/binary.md5"
    ls -la "$BIN"; echo "md5 $(cat "$E/binary.md5")"; echo "SystemLanguage strings: $(strings "$BIN" | grep -c SystemLanguage)"
  fi
  exit $rc
  ;;
*) echo "usage: run0337.sh build"; exit 2 ;;
esac
