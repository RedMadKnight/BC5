#!/usr/bin/env bash
# BC5 experiment 0332: the extended crash dump (patch0332.py) as a private binary, and the test shortcut pointed at it.
#   build     patch the tree's runtimeLinker.cpp (md5 f294dfc2) into ~/bc5-work/exp0332/src/runtimeLinker.0332.cpp and link
#             ~/bc5-work/exp0332/kyty_emulator from the shared normal build's objects plus exp 0330's bc5LleAgc.cpp.o
#             (build0332.py, nice 19, a fresh compdb.json from ninja). No emulator, no GPU; the shared build, its objects,
#             exp 0330's files and ~/src/KytyPlus are only read. Its md5 goes to ~/bc5-work/exp0332/binary.md5.
#   shortcut  the test shortcut's host wrapper ~/bc5-work/exp0330/test0330p.sh runs this binary instead of exp 0330's
#             (one line, BC5_EMU=), and the shortcut is renamed "BC5 emulator (test 0332: crash przy śmierci)". Backups go
#             to ~/bc5-work/exp0332/shortcut-before/. The launcher copy, the sampler and the 0330 switches stay as they are.
# usage: run0332.sh build | shortcut   (on the box, with patch0332.py and build0332.py in ~/bc5-work/exp0332)
set -u
E=$HOME/bc5-work/exp0332; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
K=$HOME/src/KytyPlus; B=$HOME/bc5-work/kytyplus-build; BIN=$E/kyty_emulator
TREE_MD5=f294dfc28ec7558552d6b3898dbde71d
md5() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$R" "$E/src"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
case "${1:-}" in
build)
  [ "$(md5sum < "$K/src/loader/runtimeLinker.cpp" | cut -c1-32)" = "$TREE_MD5" ] || { echo "the tree's runtimeLinker.cpp is not f294dfc2: stop"; exit 1; }
  [ "$(md5 "$B/src/kyty_emulator")" = 4a146894 ] || { echo "the shared normal build is not 4a146894: stop"; exit 1; }
  echo "cloud exp 0332 | build of ~/bc5-work/exp0332/kyty_emulator (one unit + link, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0332 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  { echo "tree runtimeLinker.cpp $(stat -c '%y' "$K/src/loader/runtimeLinker.cpp") md5 $TREE_MD5"
    echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(md5 "$B/src/kyty_emulator")"
    echo "exp 0330 object $(stat -c '%y' "$HOME/bc5-work/exp0330/obj/bc5LleAgc.cpp.o") md5 $(md5 "$HOME/bc5-work/exp0330/obj/bc5LleAgc.cpp.o")"; } > "$R/build-inputs.txt"
  python3 -I "$E/patch0332.py" "$K/src/loader/runtimeLinker.cpp" "$E/src/runtimeLinker.0332.cpp" "$R/patch_0332.diff" || exit 1
  echo "== $(date +%T) compdb"
  distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
  grep -q '"output": "src/kyty_emulator"' "$E/compdb.json" || { echo "no link command in the compdb"; exit 1; }
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0332.py" "$E/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  echo "== $(date +%T) build rc $rc" | tee -a "$R/build.out"
  echo "warnings: $(grep -c "warning:" "$R/build.out")"
  grep -A3 "runtimeLinker.0332.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  if [ "$rc" = 0 ] && [ -x "$BIN" ]; then
    md5 "$BIN" > "$E/binary.md5"
    ls -la "$BIN"; echo "md5 $(cat "$E/binary.md5")"; echo "frame-dump strings: $(strings "$BIN" | grep -c 'frame \[\[rbp')"
  fi
  exit $rc
  ;;
shortcut)
  WR=$HOME/bc5-work/exp0330/test0330p.sh; DESK=$(xdg-user-dir DESKTOP 2> /dev/null); LNK="$DESK/BC5 emulator (test 0330).desktop"
  OLD='exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$E/kyty_emulator" "$E/play-pkg-0330t.sh"'
  NEW='exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU="$HOME/bc5-work/exp0332/kyty_emulator" "$E/play-pkg-0330t.sh"  # exp 0332: the extended crash dump'
  ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/(play-pkg[^ ]*|test0330p)\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
  [ -s "$E/binary.md5" ] && [ "$(md5 "$BIN")" = "$(cat "$E/binary.md5")" ] || { echo "no built $BIN: stop"; exit 1; }
  [ "$(md5 "$WR")" = 7ce287ad ] || { echo "$WR is not 7ce287ad: stop"; exit 1; }
  [ "$(grep -cxF -- "$OLD" "$WR")" = 1 ] || { echo "the wrapper's exec line is not there once: stop"; exit 1; }
  [ -f "$LNK" ] && grep -q '^Name=BC5 emulator (test 0330: pamięć)$' "$LNK" || { echo "the shortcut is not the test 0330 one: stop"; exit 1; }
  [ -e "$E/shortcut-before" ] && { echo "$E/shortcut-before exists: stop"; exit 1; }
  echo "cloud exp 0332 | the test shortcut to the 0332 binary (files only, no emulator) | start $(date +%H:%M) | until ~$(date -d +3min +%H:%M)" > "$LOCK"
  trap 'grep -q "^cloud exp 0332 | the test shortcut" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
  mkdir -p "$E/shortcut-before" && cp -p "$WR" "$E/shortcut-before/test0330p.sh" && cp -p "$LNK" "$E/shortcut-before/BC5 emulator (test 0330).desktop" || exit 1
  restore() { cat "$E/shortcut-before/test0330p.sh" > "$WR"; cat "$E/shortcut-before/BC5 emulator (test 0330).desktop" > "$LNK"; echo "RESTORED"; exit 1; }
  awk -v o="$OLD" -v n="$NEW" '$0 == o {print n; next} {print}' "$E/shortcut-before/test0330p.sh" > "$WR.new" && cat "$WR.new" > "$WR" && rm -f "$WR.new" || restore
  bash -n "$WR" || restore
  sed -e 's/^Name=BC5 emulator (test 0330: pamięć)$/Name=BC5 emulator (test 0332: crash przy śmierci)/' \
      -e 's#^Comment=.*#Comment=BC5 exp 0332: the 0330 test shortcut with the extended crash dump (private binary '"$(cat "$E/binary.md5")"'): RT as in input.cfg, the memory sampler and the zero scan at 540 s as before; logs in ~/bc5-work/exp0330/play/#' \
      "$E/shortcut-before/BC5 emulator (test 0330).desktop" > "$LNK.new" && cat "$LNK.new" > "$LNK" && rm -f "$LNK.new" || restore
  grep -q '^Name=BC5 emulator (test 0332: crash przy śmierci)$' "$LNK" || restore
  diff -u "$E/shortcut-before/test0330p.sh" "$WR" > "$R/test0330p-0332.diff"
  [ "$(grep -c '^+[^+]' "$R/test0330p-0332.diff")" = 1 ] || restore
  echo "wrapper $WR: 7ce287ad -> $(md5 "$WR") (BC5_EMU -> $BIN, $(cat "$E/binary.md5")); shortcut renamed: $(grep '^Name=' "$LNK")"
  echo "undo: cat $E/shortcut-before/test0330p.sh > $WR; cat \"$E/shortcut-before/BC5 emulator (test 0330).desktop\" > \"$LNK\""
  ;;
*) echo "usage: run0332.sh build | shortcut"; exit 2 ;;
esac
