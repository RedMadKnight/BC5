#!/usr/bin/env bash
# BC5 (2026-10-25, the maintainer asked): log the maintainer's user straight into the Plasma (Wayland) session at
# every boot, so the box is ready for the launchers after a power cut (a remote power plug that switches the BC-250
# off and on; the board starts by itself when power returns).
#
# The box (Bazzite 44, Kinoite) uses plasma-login-manager (plasmalogin.service). Its
# /etc/plasmalogin.conf.d/99-plasma-setup.conf still asks for an autologin of the first-boot user plasma-setup,
# which fails at every boot ("Autologin failed!" in journalctl -u plasmalogin) and leaves the greeter. This moves
# that file aside (kept under backup/) and adds 90-bc5-autologin.conf for the maintainer's user.
#
# Note: with autologin, anyone at the box's keyboard gets the desktop without a password.
# usage: sudo bash install.sh            undo: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
U=${BC5_AUTOLOGIN_USER:-kjaniszewski}
id "$U" > /dev/null || { echo "no user $U"; exit 1; }
[ -f /usr/share/wayland-sessions/plasma.desktop ] || { echo "no /usr/share/wayland-sessions/plasma.desktop"; exit 1; }
systemctl is-enabled plasmalogin.service > /dev/null 2>&1 || { echo "plasmalogin.service is not the display manager here"; exit 1; }
D=/etc/plasmalogin.conf.d
B="$(cd "$(dirname "$0")" && pwd)/backup"
mkdir -p "$D" "$B"
if [ -f "$D/99-plasma-setup.conf" ]; then
  cp -a "$D/99-plasma-setup.conf" "$B/99-plasma-setup.conf"
  rm "$D/99-plasma-setup.conf"
  echo "moved $D/99-plasma-setup.conf to $B/"
fi
cat > "$D/90-bc5-autologin.conf" << EOF
# BC5 (2026-10-25, the maintainer asked): log $U into Plasma (Wayland) at boot. Undo: sudo bash undo.sh
[Autologin]
User=$U
Session=plasma
EOF
chmod 644 "$D/90-bc5-autologin.conf"
echo "done: the next boot logs $U into Plasma (Wayland)."
echo "check after a reboot: journalctl -b -u plasmalogin | grep -i autologin   (no \"Autologin failed!\")"
