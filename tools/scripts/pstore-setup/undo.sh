#!/usr/bin/env bash
# BC5: undo install.sh. The kernel argument goes away at the next boot; the copy unit is removed now. The records
# already copied to ~/bc5-data/captures/pstore/ stay.
# usage: sudo bash undo.sh   (then reboot)
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
rpm-ostree kargs --delete-if-present=efi_pstore.pstore_disable=0
systemctl disable bc5-pstore-copy.service 2> /dev/null || true
rm -f /etc/systemd/system/bc5-pstore-copy.service
systemctl daemon-reload
echo "undone; reboot to drop the kernel argument."
