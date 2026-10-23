#!/usr/bin/env bash
# BC5 experiment 0226: ADR 0013's held tail. One test binary for both arms; each step started by hand (attended, one at
# a time, on the box supervisor's Go).
#   run0226.sh build               compile src/bc5LleAgc.hold.cpp, link ~/bc5-work/exp0226/kyty_emulator (build0226.py)
#                                  under a BOX-LOCK line of its own; the shared tree's file must still equal
#                                  src/bc5LleAgc.before-0226.cpp. The file name stays kyty_emulator (exp 0221).
#   run0226.sh bench <A|B> <tag> [secs]
#                                  bench0201.sh <tag> <secs, default 600> with that binary; arm A: BC5_DIRECT_HOLD_TAIL
#                                  unset (today's path), arm B: BC5_DIRECT_HOLD_TAIL=1. The old launcher values pinned
#                                  (FLAT_APERTURE=0, the old skip list; play-pkg-0194.sh never sets BC5_DIRECT_AMM_PRT),
#                                  the default 8-ms limit, no traces. 60 s in, the emulator's environment is kept in raw/.
#                                  The bench's own lock and stop end the run.
#   run0226.sh extract <tag>       one nice/ionice grep of the run's journal: the lines the comparison reads
# Before build and bench: the boot id is still the one of the first call (raw/boot.txt) and no new amdgpu
# fault/timeout/reset/error line has appeared in dmesg since then.
set -u
E=$HOME/bc5-work/exp0226; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus; BIN=$E/kyty_emulator
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
build)
  box_free && checks || exit 1
  cmp -s "$K/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.before-0226.cpp" || { echo "the tree's bc5LleAgc.cpp changed: stop"; exit 1; }
  echo "tcp exp 0226 | build of ~/bc5-work/exp0226/kyty_emulator (one unit + link, nice 19) | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
  echo "== $(date +%T) build"
  ( cd "$E" && distrobox enter ubuntu -- python3 -I "$E/build0226.py" "$HOME/bc5-work/exp0203/compdb.json" ) > "$R/build.out" 2>&1
  rc=$?
  grep -q "^tcp exp 0226 | build" "$LOCK" 2> /dev/null && rm -f "$LOCK"
  echo "== $(date +%T) build rc $rc; BOX-LOCK removed"
  grep -c "warning:" "$R/build.out"
  grep -A3 "bc5LleAgc.hold.cpp:[0-9]*:[0-9]*: .*\(warning\|error\)" "$R/build.out" | grep -v "^--" | sed 's/\x1b\[[0-9;]*m//g' | head -30
  ls -la "$BIN" 2> /dev/null && strings "$BIN" | grep -c "hold tail: "
  exit $rc
  ;;
bench)
  ARM=${2:-}; TAG=${3:-}; SECS=${4:-600}
  [ "$ARM" = A ] || [ "$ARM" = B ] || { echo "arm A or B"; exit 2; }
  [ -n "$TAG" ] || { echo "a tag"; exit 2; }
  [ ! -e "$HOME/bc5-work/exp0194/r-$TAG" ] || { echo "tag $TAG used"; exit 1; }
  box_free && checks || exit 1
  [ -x "$BIN" ] || { echo "no binary"; exit 1; }
  HX=""; [ "$ARM" = B ] && HX="BC5_DIRECT_HOLD_TAIL=1"
  echo "$ARM" > "$R/$TAG-arm.txt"
  ( for _ in $(seq 1 60); do p=$(pgrep -n -x kyty_emulator) && break; sleep 2; done; sleep 50; p=$(pgrep -n -x kyty_emulator) && tr '\0' '\n' < /proc/$p/environ | grep -E '^BC5_DIRECT_(FLAT_APERTURE|AMM_PRT|SKIP_PGM|HOLD_TAIL|HOLD_TAIL_MS|DCB_WAIT_MS|CHAIN|COMPUTE_RING|CROSS_RING_WAITS)=|^BC5_EMU=' > "$R/$TAG-environ.txt" ) &
  ENVX="BC5_EMU=$BIN BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_SKIP_PGM=$OLD_SKIP $HX" "$HOME/bc5-work/exp0201/bench0201.sh" "$TAG" "$SECS" > "$R/$TAG-bench.out" 2>&1
  echo "== $(date +%T) bench $TAG (arm $ARM) rc $?"
  cat "$R/$TAG-bench.out"
  wait; echo "-- environment 60 s in:"; cat "$R/$TAG-environ.txt"
  ;;
extract)
  TAG=${2:-}
  j=$(grep -ao "journal /[^ ;]*" "$HOME/bc5-work/exp0201/$TAG.out" | head -1 | cut -d" " -f2)
  [ -d "$j" ] && j=$j/direct.log
  [ -f "$j" ] || { echo "no journal ($j)"; exit 1; }
  echo "$j" > "$R/$TAG-journal-path.txt"
  nice -n 19 ionice -c3 grep -aE '^hold tail: |^cpu-wait |^two rings|^chains: |^frame profile: t |TIMEOUT|^timeout' "$j" > "$R/$TAG-extract.txt"
  cp "$HOME/bc5-work/exp0194/r-$TAG/emu.log" "$R/$TAG-emu.log" 2> /dev/null
  echo "== $(date +%T) extract $TAG: $(wc -l < "$R/$TAG-extract.txt") lines; GIVEN UP $(grep -c 'GIVEN UP' "$R/$TAG-extract.txt"), hold tail $(grep -c '^hold tail: ' "$R/$TAG-extract.txt")"
  ;;
*)
  echo "usage: run0226.sh build | bench <A|B> <tag> [secs] | extract <tag>"; exit 2 ;;
esac
