#!/usr/bin/env bash
# BC5 experiment 0225: exp 0224's binary and traces at the 100-ms game-thread wait limit (BC5_DIRECT_DCB_WAIT_MS=100, as
# exps 0207/0208 ran it). No build. Each step is started by hand (attended, one at a time, on the box supervisor's Go).
#   run0225.sh bench    bench0201.sh tcpW9 600 with ~/bc5-work/exp0224/kyty_emulator: BC5_DIRECT_DCB_WAIT_MS=100,
#                       BC5_DIRECT_WAIT_TRACE=1, BC5_DIRECT_FLIP_TRACE=1 with exp 0221's breakpoints on its four compute
#                       labels, BC5_DIRECT_DOORBELL_TRACE=1; the old launcher values pinned (FLAT_APERTURE=0, the old skip
#                       list; play-pkg-0194.sh never sets BC5_DIRECT_AMM_PRT). 60 s in, the emulator's environment is kept
#                       in raw/. The bench's own lock and stop end the run.
#   run0225.sh extract  one nice/ionice grep of the run's journal: the lines the analyses read
# Before bench: the boot id is still the one of the first call (raw/boot.txt) and no new amdgpu fault/timeout/reset/error
# line has appeared in dmesg since then.
set -u
E=$HOME/bc5-work/exp0225; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; TAG=${TAG:-tcpW9}; BIN=$HOME/bc5-work/exp0224/kyty_emulator
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
bench)
  box_free && checks || exit 1
  [ -x "$BIN" ] || { echo "no binary"; exit 1; }
  ( for _ in $(seq 1 60); do p=$(pgrep -n -x kyty_emulator) && break; sleep 2; done; sleep 50; p=$(pgrep -n -x kyty_emulator) && tr '\0' '\n' < /proc/$p/environ | grep -E '^BC5_DIRECT_(FLAT_APERTURE|AMM_PRT|SKIP_PGM|FLIP_TRACE|FLIP_TRACE_WP|FLIP_TRACE_WP_LABELS|DOORBELL_TRACE|WAIT_TRACE|DCB_WAIT_MS)=|^BC5_EMU=' > "$R/$TAG-environ.txt" ) &
  ENVX="BC5_EMU=$BIN BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_SKIP_PGM=$OLD_SKIP BC5_DIRECT_DCB_WAIT_MS=100 BC5_DIRECT_WAIT_TRACE=1 BC5_DIRECT_FLIP_TRACE=1 BC5_DIRECT_FLIP_TRACE_WP=1 BC5_DIRECT_FLIP_TRACE_WP_LABELS=$WPL BC5_DIRECT_DOORBELL_TRACE=1" "$HOME/bc5-work/exp0201/bench0201.sh" "$TAG" 600 > "$R/$TAG-bench.out" 2>&1
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
  echo "== $(date +%T) extract: $(wc -l < "$R/$TAG-extract.txt") lines; flip $(grep -c '^flip trace: ' "$R/$TAG-extract.txt"), doorbell $(grep -c '^doorbell trace: ' "$R/$TAG-extract.txt"), ts $(grep -c '^ts trace: ' "$R/$TAG-extract.txt"), served $(grep -c '^flip trace: served' "$R/$TAG-extract.txt")"
  ;;
*)
  echo "usage: run0225.sh bench|extract"; exit 2 ;;
esac
