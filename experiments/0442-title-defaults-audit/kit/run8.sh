#!/usr/bin/env bash
# exp 0442 run 8 (D28, the top session 20:33): perf stat of the kept old lean (C, 05fd749d) and the new shared lean
# (N, b0f856ed, bake 1c+1d) on the first title: a discarded warm-up (W0, the old lean), then C N / N C (ab442r, 2 rounds).
# Each emulator gets one perf stat attached 40 s after it appears, counting 100 s (inside MangoHud's window from 30 s),
# per thread, user space only (perf_event_paranoid 2, nothing changed): task-clock, cycles, instructions, branch-misses,
# L1-icache-load-misses, iTLB-load-misses. perf from the ubuntu distrobox (7.0.14). Plus ab442c's memory sampler.
set -u
W=$HOME/bc5-work; X=$W/exp0442; P=$X/perf8; mkdir -p "$P"
OL=$X/swap/kyty_emulator.lean.before-0442; NL=$W/kytyplus-build-lean/src/kyty_emulator
MO=$(md5sum < "$OL" | cut -c1-8); ML=$(md5sum < "$NL" | cut -c1-8)
[ "$MO" = 05fd749d ] && [ "$ML" = b0f856ed ] || { echo "run8: binaries $MO / $ML, not 05fd749d / b0f856ed"; exit 1; }
pf() {
  local seen=""
  while :; do
    for p in $(pgrep '^kyty_emulator'); do
      case " $seen " in *" $p "*) continue ;; esac
      seen="$seen $p"
      ( sleep 40; x=$(readlink /proc/$p/exe 2>/dev/null); m=$(md5sum < "/proc/$p/exe" 2>/dev/null | cut -c1-8)
        echo "# pid $p exe $x md5 $m start $(date +%T)" > "$P/perf-$p.csv"
        distrobox enter ubuntu -- perf stat -x, --per-thread -e task-clock,cycles:u,instructions:u,branch-misses:u,L1-icache-load-misses:u,iTLB-load-misses:u \
          -p "$p" -- sleep 100 >> "$P/perf-$p.csv" 2>&1 < /dev/null
        echo "# end $(date +%T)" >> "$P/perf-$p.csv" ) &
    done
    sleep 2
  done
}
pf & PF=$!
trap 'kill $PF 2>/dev/null' EXIT
AB_CB=$OL AB_OB=$NL AB_NB=$NL AB_PIN_C=$MO AB_PIN_O=$ML AB_PIN_N=$ML AB_WARMUP=1 AB_ROUNDS=2 AB_ARMS="C N" AB_ARM_C="$OL|$MO|" AB_ARM_N="$NL|$ML|" \
  MEMF=ab-mem-r8.txt bash "$X/ab442c.sh" "q442p8$(date +%H%M)"
