#!/usr/bin/env bash
# BC5: undo install.sh, so the box shows the login screen at boot again (and plasma-setup's file is back).
# usage: sudo bash undo.sh
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
D=/etc/plasmalogin.conf.d
B="$(cd "$(dirname "$0")" && pwd)/backup"
rm -f "$D/90-bc5-autologin.conf"
[ -f "$B/99-plasma-setup.conf" ] && cp -a "$B/99-plasma-setup.conf" "$D/99-plasma-setup.conf" && echo "restored $D/99-plasma-setup.conf"
echo "done: the next boot shows the login screen."
