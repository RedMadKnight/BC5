#!/usr/bin/env bash
# BC5: when the running emulator journal stops growing for 8 s, save thread stacks once (eu-stack).
OUT=$1; sleep 40; last=-1; same=0
while pid=$(pgrep -x kyty_emulator); do
  L=$(cat ~/bc5-work/last-kytyplus)/gc/direct.log; s=$(stat -c %s "$L" 2>/dev/null || echo 0)
  if [ "$s" = "$last" ]; then same=$((same+1)); else same=0; last=$s; fi
  if [ $same -ge 4 ]; then eu-stack -p "$pid" > "$OUT" 2>&1; echo "stacks at $(date +%T)" >> "$OUT"; exit 0; fi
  sleep 2
done
