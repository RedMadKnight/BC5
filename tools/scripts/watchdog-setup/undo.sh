#!/usr/bin/env bash
# BC5: undo install.sh. systemd stops feeding the hardware watchdog, and the kernel's panic settings go back to the
# values install.sh found (kept in /etc/sysctl.d/.bc5-panic.before; without that file: panic 0, no panic on an
# oops or a lockup).
# usage: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
O=/etc/sysctl.d/.bc5-panic.before
rm -f /etc/systemd/system.conf.d/90-bc5-watchdog.conf /etc/sysctl.d/90-bc5-panic.conf
if [ -s "$O" ]; then
  sysctl -q -p "$O"
  rm -f "$O"
else
  sysctl -q -w kernel.panic=0 kernel.panic_on_oops=0 kernel.softlockup_panic=0 kernel.hardlockup_panic=0
fi
systemctl daemon-reexec
echo "undone:"
systemctl show -p RuntimeWatchdogUSec
sysctl kernel.panic kernel.panic_on_oops kernel.softlockup_panic kernel.hardlockup_panic
