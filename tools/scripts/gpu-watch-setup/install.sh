#!/usr/bin/env bash
# BC5 (2026-10-27): install bc5-gpu-watch.sh (beside this file) as a root service. It reboots the box through a SysRq
# crash when an amdgpu ring timeout or GPU reset is not followed by a reset that succeeded within 60 s; see the script's
# header for why (13:29 that day: a reset that never finished, 26 minutes of a stalled box, no reboot). It works
# together with tools/scripts/watchdog-setup (panic on oops, reboot 10 s after a panic) and tools/scripts/pstore-setup
# (the panic's kernel log kept).
# usage: sudo bash install.sh            undo: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE/bc5-gpu-watch.sh" ] || { echo "no bc5-gpu-watch.sh beside this script"; exit 1; }
[ "$(sysctl -n kernel.panic_on_oops)" = 1 ] || echo "note: kernel.panic_on_oops is not 1: the SysRq crash will not reboot by itself (the script then reboots outright 30 s later); install tools/scripts/watchdog-setup"
install -m 755 "$HERE/bc5-gpu-watch.sh" /usr/local/sbin/bc5-gpu-watch.sh
cat > /etc/systemd/system/bc5-gpu-watch.service << 'EOF'
# BC5 (2026-10-27): reboot the box when an amdgpu reset does not finish (the kernel has no hung-task detector).
# Undo: undo.sh in tools/scripts/gpu-watch-setup
[Unit]
Description=BC5: reboot when an amdgpu reset does not finish
After=systemd-modules-load.service

[Service]
ExecStart=/usr/local/sbin/bc5-gpu-watch.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
chmod 644 /etc/systemd/system/bc5-gpu-watch.service
systemctl daemon-reload
systemctl enable bc5-gpu-watch.service
systemctl restart bc5-gpu-watch.service   # a second run takes the new script
sleep 1
systemctl --no-pager --lines=0 status bc5-gpu-watch.service | head -4
echo "done. Its own lines are in the kernel ring buffer: sudo dmesg | grep bc5-gpu-watch (journalctl -k does not show them)"
dmesg | grep bc5-gpu-watch | tail -2
