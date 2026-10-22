#!/usr/bin/env bash
# BC5 experiment 0192, second form of catch-play.sh: dump the GPU waves once only when a stall is a fault. While a
# "kyty_emulator --game" process runs (a journal created after arming, its first SKIP seconds skipped), each time
# the journal has not grown for STILL ms the kernel log is read (sudoers: dmesg); only if it holds a GPU page fault
# newer than the arming (a count above the one at arming) are the waves dumped (sudoers: umr -O halt_waves -wa
# gfx_0.0.0), before the kernel's 2-s ring reset. Slow frames (the 1.2-s GPU jobs of the 08:14 catch) dump nothing.
# The dump, the kernel log and the journal tail are synced at once (a reset may take the machine down).
# usage: catch-fault.sh <out dir> [skip s] [max s] [still ms, default 500]
OUT=$1; SKIP=${2:-15}; MAX=${3:-7200}; STILL=${4:-500}
mkdir -p "$OUT"; touch "$OUT/armed"
log() { echo "$(date +%T) $*" >> "$OUT/catch.log"; sync; }
faults() { sudo -n dmesg 2>/dev/null | grep -c "page fault"; }
F0=$(faults)
log "armed (skip $SKIP s, max $MAX s, still $STILL ms, kernel page-fault lines at arming: $F0)"
END=$(( $(date +%s) + MAX )); J=""; JT=0; last=-1; since=$(date +%s%N); k=0; checked=0
while [ "$(date +%s)" -lt "$END" ]; do
  if [ $(( k % 20 )) = 0 ]; then # every ~2 s: a newer journal?
    N=$(ls -td ~/bc5-data/captures/play-*/ 2>/dev/null | head -3 | while read -r d; do f=${d}gc/direct.log; [ "$f" -nt "$OUT/armed" ] && echo "$f"; done | head -1)
    if [ -n "$N" ] && [ "$N" != "$J" ]; then J=$N; JT=$(date +%s); last=-1; since=$(date +%s%N); log "journal $J"; fi
  fi
  k=$((k + 1))
  if [ -n "$J" ] && [ $(( $(date +%s) - JT )) -ge "$SKIP" ] && pgrep -f "kyty_emulator --game" >/dev/null; then
    s=$(stat -c %s "$J" 2>/dev/null); now=$(date +%s%N)
    if [ "$s" != "$last" ]; then last=$s; since=$now; checked=0
    elif [ $(( now - since )) -gt $(( STILL * 1000000 )) ] && [ $(( now - checked )) -gt 150000000 ]; then
      checked=$now; F=$(faults)
      if [ "$F" -gt "$F0" ]; then
        { echo "journal still for $(( (now - since) / 1000000 )) ms at $(date +%T.%N), kernel page-fault lines $F0 -> $F: $J"; sudo -n /usr/bin/umr -O halt_waves -wa gfx_0.0.0; } > "$OUT/waves.txt" 2>&1; sync
        log "waves dumped (page-fault lines $F0 -> $F)"
        sudo -n dmesg 2>&1 | tail -300 > "$OUT/dmesg-tail.txt"; tail -c 300000 "$J" > "$OUT/journal-tail.txt"; sync
        log "kernel log and journal tail saved"; exit 0
      fi
    fi
  else
    since=$(date +%s%N); [ -n "$J" ] && last=$(stat -c %s "$J" 2>/dev/null)
  fi
  sleep 0.1
done
log "window over, no faulting stall caught"
