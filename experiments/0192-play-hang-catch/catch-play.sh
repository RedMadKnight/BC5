#!/usr/bin/env bash
# BC5 experiment 0192: a dedicated catch session (F229: GPU wave dumps only in sessions armed for it). Waits for the
# next game session's direct journal (a capture created after arming; the menu window has none), skips its first
# SKIP seconds (start-up), then, while a "kyty_emulator --game" process runs, dumps the GPU waves once
# (sudoers: umr -O halt_waves -wa gfx_0.0.0) when the journal has not grown for 0.7 s — before the kernel's 2-s ring
# reset — and saves the kernel log tail and the journal tail; everything is synced at once (the reset may take the
# machine down). A new journal (the game restarted) is followed; the game ending stops nothing (the next one is
# watched) until MAX seconds after arming.
# usage: catch-play.sh <out dir> [skip s] [max s] [still ms, default 700]
OUT=$1; SKIP=${2:-15}; MAX=${3:-7200}; STILL=${4:-700}
mkdir -p "$OUT"; touch "$OUT/armed"
log() { echo "$(date +%T) $*" >> "$OUT/catch.log"; sync; }
log "armed (skip $SKIP s, max $MAX s, still $STILL ms)"
END=$(( $(date +%s) + MAX )); J=""; JT=0; last=-1; since=$(date +%s%N); k=0
while [ "$(date +%s)" -lt "$END" ]; do
  if [ $(( k % 20 )) = 0 ]; then # every ~2 s: a newer journal?
    N=$(ls -td ~/bc5-data/captures/play-*/ 2>/dev/null | head -3 | while read -r d; do f=${d}gc/direct.log; [ "$f" -nt "$OUT/armed" ] && echo "$f"; done | head -1)
    if [ -n "$N" ] && [ "$N" != "$J" ]; then J=$N; JT=$(date +%s); last=-1; since=$(date +%s%N); log "journal $J"; fi
  fi
  k=$((k + 1))
  if [ -n "$J" ] && [ $(( $(date +%s) - JT )) -ge "$SKIP" ] && pgrep -f "kyty_emulator --game" >/dev/null; then
    s=$(stat -c %s "$J" 2>/dev/null); now=$(date +%s%N)
    if [ "$s" != "$last" ]; then last=$s; since=$now
    elif [ $(( now - since )) -gt $(( STILL * 1000000 )) ]; then
      { echo "journal still for $STILL ms at $(date +%T.%N): $J"; sudo -n /usr/bin/umr -O halt_waves -wa gfx_0.0.0; } > "$OUT/waves.txt" 2>&1; sync
      log "waves dumped"
      sudo -n dmesg 2>&1 | tail -300 > "$OUT/dmesg-tail.txt"; tail -c 300000 "$J" > "$OUT/journal-tail.txt"; sync
      log "kernel log and journal tail saved"; exit 0
    fi
  else
    since=$(date +%s%N); [ -n "$J" ] && last=$(stat -c %s "$J" 2>/dev/null)
  fi
  sleep 0.1
done
log "window over, no stall caught"
