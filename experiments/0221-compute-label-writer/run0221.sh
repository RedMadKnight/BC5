#!/usr/bin/env bash
# BC5 experiment 0221: the steps of the slot, each started by hand (attended, one at a time, on the box supervisor's Go).
#   run0221.sh wptest   compile and run wptest0221.cpp in the ubuntu distrobox (where the emulator runs): do counting
#                       write breakpoints work there? (one process, three threads, no GPU, a second)
#   run0221.sh build    compile src/bc5LleAgc.v2.cpp and link ~/bc5-work/exp0221/kyty_emulator (build0221.py) under a
#                       BOX-LOCK line of its own; the shared tree's file must still equal src/bc5LleAgc.before-0221.cpp
#   run0221.sh bench    bench0201.sh tcpW6 600 with that binary, BC5_DIRECT_WAIT_TRACE=1, BC5_DIRECT_FLIP_TRACE=1 and
#                       (unless WP=0) BC5_DIRECT_FLIP_TRACE_WP=1; the old launcher values pinned (FLAT_APERTURE=0, the old
#                       skip list; bench0201 goes through exp 0194's play-pkg-0194.sh, which never sets BC5_DIRECT_AMM_PRT).
#                       60 s in, the emulator's environment is checked and kept in raw/
#   run0221.sh extract  one nice/ionice grep of the run's journal: the lines the analyses read
# Before wptest, build and bench: the boot id is still the one of the first call (raw/boot.txt) and no new amdgpu
# fault/timeout/reset/error line has appeared in dmesg since then.
set -u
E=$HOME/bc5-work/exp0221; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
V=${V:-v2}  # v2: patch0221.py, kyty_emulator, tcpW6; v3: patch0221b.py, kyty_emulator-v3, tcpW7
if [ "$V" = v3 ]; then TAG=${TAG:-tcpW7}; BIN=$E/kyty_emulator-v3; BUILD=build0221b.py; SRCF=bc5LleAgc.v3.cpp; else TAG=${TAG:-tcpW6}; BIN=$E/kyty_emulator; BUILD=build0221.py; SRCF=bc5LleAgc.v2.cpp; fi
WPL=${WPL:-0x12004b37c8,0x12004b53c8,0x12004b4fc8,0x12004b77c8}  # v3: the compute labels with write breakpoints (tcpW5/W6's four most often held back)
OLD_SKIP=11d049aa00,11d04a6000,909974400,11d04bb900
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
wptest)
  box_free && checks || exit 1
  ( cd "$E" && distrobox enter ubuntu -- sh -c "g++ -O1 -pthread -o wptest0221 wptest0221.cpp && ./wptest0221" ) > "$R/wptest.out" 2>&1
  echo "== $(date +%T) wptest rc $?"; cat "$R/wptest.out"
  ;;
build)
  box_free && checks || exit 1
  cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.before-0221.cpp" || { echo "the tree's bc5LleAgc.cpp changed: stop"; exit 1; }
  echo "tcp exp 0221 | build of ~/bc5-work/exp0221/$(basename "$BIN") ($V: one unit + link, nice 19) | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/$BUILD" "$HOME/bc5-work/exp0203/compdb.json" ) > "$R/build-$V.out" 2>&1
  rc=$?
  grep -q "^tcp exp 0221 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"
  echo "== $(date +%T) build rc $rc; BOX-LOCK removed"
  grep -c "warning:" "$R/build-$V.out"
  grep -A3 "$SRCF:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build-$V.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -20
  ls -la "$BIN" 2> /dev/null && strings "$BIN" | grep -c "flip trace: "
  exit $rc
  ;;
bench)
  box_free && checks || exit 1
  [ -x "$BIN" ] || { echo "no binary"; exit 1; }
  WPX="BC5_DIRECT_FLIP_TRACE_WP=1"; [ "$V" = v3 ] && WPX="$WPX BC5_DIRECT_FLIP_TRACE_WP_LABELS=$WPL"; [ "${WP:-1}" = 0 ] && WPX=""
  ( sleep 60; p=$(pgrep -n -x kyty_emulator) && tr '\0' '\n' < /proc/$p/environ | grep -E '^BC5_DIRECT_(FLAT_APERTURE|AMM_PRT|SKIP_PGM|FLIP_TRACE|FLIP_TRACE_WP|FLIP_TRACE_WP_LABELS|WAIT_TRACE|DCB_WAIT_MS)=|^BC5_EMU=' > "$R/$TAG-environ.txt" ) &
  ENVX="BC5_EMU=$BIN BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_SKIP_PGM=$OLD_SKIP BC5_DIRECT_WAIT_TRACE=1 BC5_DIRECT_FLIP_TRACE=1 $WPX" "$HOME/bc5-work/exp0201/bench0201.sh" "$TAG" 600 > "$R/$TAG-bench.out" 2>&1
  echo "== $(date +%T) bench rc $?"
  cat "$R/$TAG-bench.out"; tail -4 "$HOME/bc5-work/exp0201/$TAG.out"
  wait; echo "-- environment 60 s in:"; cat "$R/$TAG-environ.txt"
  ;;
extract)
  j=$(grep -ao "journal /[^ ;]*" "$HOME/bc5-work/exp0201/$TAG.out" | head -1 | cut -d" " -f2)
  [ -d "$j" ] && j=$j/direct.log
  [ -f "$j" ] || { echo "no journal ($j)"; exit 1; }
  echo "$j" > "$R/$TAG-journal-path.txt"
  nice -n 19 ionice -c3 grep -aE '^flip trace: |^cpu-wait |^  wait detail: |^wait trace: t |^timing: t [0-9.]+ s after that wait|^timing: #|^frame profile: t ' "$j" > "$R/$TAG-extract.txt"
  echo "== $(date +%T) extract: $(wc -l < "$R/$TAG-extract.txt") lines, $(grep -c '^flip trace: ' "$R/$TAG-extract.txt") flip-trace lines"
  ;;
*)
  echo "usage: run0221.sh wptest|build|bench|extract"; exit 2 ;;
esac
