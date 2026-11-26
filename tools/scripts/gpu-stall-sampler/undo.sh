#!/usr/bin/env bash
# BC5 (exp 0373): undo install.sh: stop, disable and remove bc5-gpu-stall-sampler.service and its script.
# The captures in ~/bc5-data/captures/gpu-stall/ stay.
# usage: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
systemctl disable --now bc5-gpu-stall-sampler.service 2> /dev/null || true
rm -f /etc/systemd/system/bc5-gpu-stall-sampler.service /usr/local/sbin/bc5-gpu-stall-sampler
systemctl daemon-reload
echo "undone: bc5-gpu-stall-sampler removed (captures kept)"
