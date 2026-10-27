#!/usr/bin/env bash
# BC5 (2026-10-27, exp 0340 arm 0): keep the kernel's last lines across a hang. The box's machine-downs end the
# journal before the GPU reset's own lines (F413): the journal on disk loses its last minute. With the watchdog
# setup (tools/scripts/watchdog-setup) a lockup or an oops becomes a panic. With efi-pstore on, the panic writes the
# kernel log's tail into UEFI variables. At the next boot systemd-pstore.service moves it to
# /var/lib/systemd/pstore/, and this script's unit copies it to ~/bc5-data/captures/pstore/ (the maintainer's user,
# mode 600), next to the GPU coredumps.
#
# The box (Bazzite, rpm-ostree) has efi_pstore built in but disabled (efi_pstore.pstore_disable=Y). This adds the
# kernel argument efi_pstore.pstore_disable=0, which takes effect at the next boot.
# usage: sudo bash install.sh   (then reboot)            undo: sudo bash undo.sh   (then reboot)
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
[ -d /sys/firmware/efi ] || { echo "not booted with UEFI: efi-pstore cannot work"; exit 1; }
command -v rpm-ostree > /dev/null || { echo "no rpm-ostree: add efi_pstore.pstore_disable=0 to the kernel command line by hand"; exit 1; }
U=${BC5_PSTORE_USER:-kjaniszewski}
H=$(getent passwd "$U" | cut -d: -f6)
[ -n "$H" ] || { echo "no user $U"; exit 1; }
rpm-ostree kargs --append-if-missing=efi_pstore.pstore_disable=0
systemctl enable systemd-pstore.service 2> /dev/null || true
cat > /etc/systemd/system/bc5-pstore-copy.service << EOF
# BC5 (2026-10-27, exp 0340 arm 0): copy the kernel's panic records that systemd-pstore saved to the maintainer's
# captures directory. Undo: undo.sh in tools/scripts/pstore-setup
[Unit]
Description=BC5: copy pstore panic records to $H/bc5-data/captures/pstore
After=systemd-pstore.service
ConditionDirectoryNotEmpty=/var/lib/systemd/pstore

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'd=$H/bc5-data/captures/pstore; mkdir -p "\$\$d"; cp -rn /var/lib/systemd/pstore/. "\$\$d/"; chown -R $U: "\$\$d"; chmod -R go-rwx "\$\$d"; logger -t bc5-pstore "copied pstore records to \$\$d"'

[Install]
WantedBy=multi-user.target
EOF
chmod 644 /etc/systemd/system/bc5-pstore-copy.service
systemctl daemon-reload
systemctl enable bc5-pstore-copy.service
echo "done. Reboot to take efi_pstore.pstore_disable=0 into effect, then check:"
echo "  cat /proc/cmdline | tr ' ' '\\n' | grep pstore        (efi_pstore.pstore_disable=0)"
echo "  cat /sys/module/efi_pstore/parameters/pstore_disable   (N)"
echo "after a crash: ls ~/bc5-data/captures/pstore/ ; journalctl -b -t bc5-pstore"
