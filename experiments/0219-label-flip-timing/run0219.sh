#!/usr/bin/env bash
# BC5 experiment 0219: the steps of the slot, each started by hand (attended, one at a time, on the box supervisor's Go).
#   run0219.sh build    compile src/bc5LleAgc.flip.cpp and link ~/bc5-work/exp0219/kyty_emulator (build0219.py) under
#                       a BOX-LOCK line of its own; the shared tree's file must still equal src/bc5LleAgc.before-0219.cpp
#   run0219.sh bench    bench0201.sh tcpW5 600 with that binary, BC5_DIRECT_WAIT_TRACE=1 and BC5_DIRECT_FLIP_TRACE=1
#                       (the bench writes and removes its own BOX-LOCK line)
#   run0219.sh extract  one nice/ionice grep of the run's journal: the lines ana0219.py reads
# Before build and bench: the boot id is still BOOT (from the first call, kept in raw/boot.txt) and no new amdgpu
# fault/timeout/reset/error line has appeared in dmesg since then.
set -u
E=$HOME/bc5-work/exp0219; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus; TAG=${TAG:-tcpW5}
mkdir -p "$R"
[ -s "$R/boot.txt" ] || { cut -c1-8 /proc/sys/kernel/random/boot_id > "$R/boot.txt"; sudo -n dmesg 2> /dev/null | wc -l > "$R/dmesg0.txt"; }
checks() {
  [ "$(cut -c1-8 /proc/sys/kernel/random/boot_id)" = "$(cat "$R/boot.txt")" ] || { echo "boot id changed: stop"; return 1; }
  local k
  k=$(sudo -n dmesg 2> /dev/null | tail -n +"$(($(cat "$R/dmesg0.txt") + 1))" | grep -ci "amdgpu.*\(fault\|timeout\|reset\|error\)")
  [ "$k" = 0 ] || { echo "$k new amdgpu lines: stop"; return 1; }
}
box_free() {
  [ ! -s "$LOCK" ] || { echo "box locked: $(cat "$LOCK")"; return 1; }
  ! pgrep -x kyty_emulator > /dev/null || { echo "an emulator runs"; return 1; }
}
case "${1:-}" in
build)
  box_free && checks || exit 1
  cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.before-0219.cpp" || { echo "the tree's bc5LleAgc.cpp changed: stop"; exit 1; }
  echo "tcp exp 0219 | build of ~/bc5-work/exp0219/kyty_emulator (one unit + link, nice 19) | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0219.py" "$HOME/bc5-work/exp0203/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  grep -q "^tcp exp 0219 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"
  echo "== $(date +%T) build rc $rc; BOX-LOCK removed"
  grep -c "warning:" "$R/build.out"
  ls -la "$E/kyty_emulator" 2> /dev/null && strings "$E/kyty_emulator" | grep -c "flip trace: "
  exit $rc
  ;;
bench)
  box_free && checks || exit 1
  [ -x "$E/kyty_emulator" ] || { echo "no binary"; exit 1; }
  ENVX="BC5_EMU=$E/kyty_emulator BC5_DIRECT_WAIT_TRACE=1 BC5_DIRECT_FLIP_TRACE=1" "$HOME/bc5-work/exp0201/bench0201.sh" "$TAG" 600 > "$R/$TAG-bench.out" 2>&1
  echo "== $(date +%T) bench rc $?"
  cat "$R/$TAG-bench.out"; tail -4 "$HOME/bc5-work/exp0201/$TAG.out"
  ;;
extract)
  j=$(grep -ao "journal /[^ ;]*" "$HOME/bc5-work/exp0201/$TAG.out" | head -1 | cut -d" " -f2)
  [ -d "$j" ] && j=$j/direct.log
  [ -f "$j" ] || { echo "no journal ($j)"; exit 1; }
  echo "$j" > "$R/$TAG-journal-path.txt"
  nice -n 19 ionice -c3 grep -aE '^flip trace: |^cpu-wait |^  wait detail: |^wait trace: t |^timing: t [0-9.]+ s after that wait' "$j" > "$R/$TAG-extract.txt"
  echo "== $(date +%T) extract: $(wc -l < "$R/$TAG-extract.txt") lines, $(grep -c '^flip trace: ' "$R/$TAG-extract.txt") flip-trace lines"
  ;;
*)
  echo "usage: run0219.sh build|bench|extract"; exit 2 ;;
esac
