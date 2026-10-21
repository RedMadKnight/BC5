#!/usr/bin/env bash
# exp 0189 (dedicated hang hunt, F229): AFTER s after the emulator starts, watch the newest direct journal; when it
# has not grown for 0.7 s, dump the GPU waves once (sudoers: umr -O halt_waves -wa gfx_0.0.0) to OUT, then exit.
AFTER=${1:-115}; OUT=$2; WINDOW=${3:-120}
for _ in $(seq 1 90); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep 3; J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
sleep "$((AFTER - 3))"
last=$(stat -c %s "$J"); since=$(date +%s%N); end=$(( $(date +%s) + WINDOW ))
while [ "$(date +%s)" -lt "$end" ] && pgrep -x kyty_emulator >/dev/null; do
  s=$(stat -c %s "$J"); now=$(date +%s%N)
  if [ "$s" != "$last" ]; then last=$s; since=$now
  elif [ $(( now - since )) -gt 700000000 ]; then
    { echo "journal still for 0.7 s at $(date +%T.%N)"; sudo -n /usr/bin/umr -O halt_waves -wa gfx_0.0.0; } > "$OUT" 2>&1
    echo "dumped $(date +%T)"; exit 0
  fi
  sleep 0.1
done
echo "no stall seen"
