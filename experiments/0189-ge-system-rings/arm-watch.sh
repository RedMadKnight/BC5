#!/usr/bin/env bash
# exp 0189: arm the root wave-dump watcher DELAY s after the emulator starts (dedicated hang hunt, F229).
DELAY=${1:-100}
for _ in $(seq 1 90); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
sleep "$DELAY"
pgrep -x kyty_emulator >/dev/null || exit 0
echo "armed $(date +%T)"
exec sudo -n /usr/local/bin/bc5-gpu-hang-watch
