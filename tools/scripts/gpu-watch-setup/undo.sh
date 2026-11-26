#!/usr/bin/env bash
# BC5: undo install.sh: stop and remove bc5-gpu-watch.service and its script.
# usage: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
systemctl disable --now bc5-gpu-watch.service 2> /dev/null || true
rm -f /etc/systemd/system/bc5-gpu-watch.service /usr/local/sbin/bc5-gpu-watch.sh
systemctl daemon-reload
echo "undone: bc5-gpu-watch removed"
