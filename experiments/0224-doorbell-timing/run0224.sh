#!/usr/bin/env bash
# BC5 experiment 0224: the steps of the slot, each started by hand (attended, one at a time, on the box supervisor's Go).
#   run0224.sh build    compile src/bc5LleAgc.v4.cpp and link ~/bc5-work/exp0224/kyty_emulator (build0224.py) under a
#                       BOX-LOCK line of its own; the shared tree's file must still equal src/bc5LleAgc.before-0224.cpp.
#                       The file name stays kyty_emulator: bench0201/run-0194b find the emulator with pgrep -x (exp 0221).
#   run0224.sh bench    bench0201.sh tcpW8 600 with that binary: BC5_DIRECT_WAIT_TRACE=1, BC5_DIRECT_FLIP_TRACE=1 with exp
#                       0221's breakpoints on its four compute labels, and BC5_DIRECT_DOORBELL_TRACE=1; the old launcher
#                       values pinned (FLAT_APERTURE=0, the old skip list; play-pkg-0194.sh never sets BC5_DIRECT_AMM_PRT).
#                       60 s in, the emulator's environment is kept in raw/. The bench's own lock and stop end the run.
#   run0224.sh extract  one nice/ionice grep of the run's journal: the lines the analyses read
# Before build and bench: the boot id is still the one of the first call (raw/boot.txt) and no new amdgpu
# fault/timeout/reset/error line has appeared in dmesg since then.
set -u
E=$HOME/bc5-work/exp0224; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus; TAG=${TAG:-tcpW8}; BIN=$E/kyty_emulator
OLD_SKIP=11d049aa00,11d04a6000,909974400,11d04bb900
WPL=${WPL:-0x12004b37c8,0x12004b53c8,0x12004b4fc8,0x12004b77c8}
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
  cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.before-0224.cpp" || { echo "the tree's bc5LleAgc.cpp changed: stop"; exit 1; }
  echo "tcp exp 0224 | build of ~/bc5-work/exp0224/kyty_emulator (one unit + link, nice 19) | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0224.py" "$HOME/bc5-work/exp0203/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  grep -q "^tcp exp 0224 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"
  echo "== $(date +%T) build rc $rc; BOX-LOCK removed"
  grep -c "warning:" "$R/build.out"
  grep -A3 "bc5LleAgc.v4.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -24
  ls -la "$BIN" 2> /dev/null && strings "$BIN" | grep -c "doorbell trace: \|ts trace: "
  exit $rc
  ;;
bench)
  box_free && checks || exit 1
  [ -x "$BIN" ] || { echo "no binary"; exit 1; }
  ( for _ in $(seq 1 60); do p=$(pgrep -n -x kyty_emulator) && break; sleep 2; done; sleep 50; p=$(pgrep -n -x kyty_emulator) && tr '\0' '\n' < /proc/$p/environ | grep -E '^BC5_DIRECT_(FLAT_APERTURE|AMM_PRT|SKIP_PGM|FLIP_TRACE|FLIP_TRACE_WP|FLIP_TRACE_WP_LABELS|DOORBELL_TRACE|WAIT_TRACE|DCB_WAIT_MS)=|^BC5_EMU=' > "$R/$TAG-environ.txt" ) &
  ENVX="BC5_EMU=$BIN BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_SKIP_PGM=$OLD_SKIP BC5_DIRECT_WAIT_TRACE=1 BC5_DIRECT_FLIP_TRACE=1 BC5_DIRECT_FLIP_TRACE_WP=1 BC5_DIRECT_FLIP_TRACE_WP_LABELS=$WPL BC5_DIRECT_DOORBELL_TRACE=1" "$HOME/bc5-work/exp0201/bench0201.sh" "$TAG" 600 > "$R/$TAG-bench.out" 2>&1
  echo "== $(date +%T) bench rc $?"
  cat "$R/$TAG-bench.out"
  wait; echo "-- environment 60 s in:"; cat "$R/$TAG-environ.txt"
  ;;
extract)
  j=$(grep -ao "journal /[^ ;]*" "$HOME/bc5-work/exp0201/$TAG.out" | head -1 | cut -d" " -f2)
  [ -d "$j" ] && j=$j/direct.log
  [ -f "$j" ] || { echo "no journal ($j)"; exit 1; }
  echo "$j" > "$R/$TAG-journal-path.txt"
  nice -n 19 ionice -c3 grep -aE '^flip trace: |^doorbell trace: |^ts trace: |^cpu-wait |^  wait detail: |^wait trace: t |^timing: t [0-9.]+ s after that wait|^timing: #|^queue [0-9]+: a ' "$j" > "$R/$TAG-extract.txt"
  echo "== $(date +%T) extract: $(wc -l < "$R/$TAG-extract.txt") lines; flip $(grep -c '^flip trace: ' "$R/$TAG-extract.txt"), doorbell $(grep -c '^doorbell trace: ' "$R/$TAG-extract.txt"), ts $(grep -c '^ts trace: ' "$R/$TAG-extract.txt")"
  ;;
*)
  echo "usage: run0224.sh build|bench|extract"; exit 2 ;;
esac
