#!/usr/bin/env bash
# BC5 (2026-10-27, the maintainer asked): when the BC-250 hangs hard, reboot it by itself instead of waiting for
# someone at the reset button. Since 2026-10-25 the box went down four times after a GPU hang (a compute-ring timeout
# whose reset never came, faults with RT on). Each time the kernel stopped logging and the board stayed hung until
# a manual reset.
#
# Two layers:
# - systemd feeds the board's hardware watchdog (SP5100 TCO, /dev/watchdog0) every RuntimeWatchdogSec/2. If the
#   kernel stops running, the timer runs out and the chipset resets the machine. RebootWatchdogSec bounds a reboot
#   that itself hangs.
# - The kernel reboots 10 s after a panic, and panics on an oops, a soft lockup or a hard lockup. Without this a
#   wedged kernel waits forever.
# A GPU hang that the kernel survives (ring reset succeeded) is not affected. Only a dead or locked-up kernel leads
# to a reboot.
#
# After a watchdog reboot the game session is lost, as it was with the manual reset, but the box comes back on its
# own: autologin (tools/scripts/autologin-setup) brings the desktop up for the launchers. The last minutes of the
# journal may still be missing; stream the kernel log from the laptop in watched runs (bc250-box-etiquette).
#
# usage: sudo bash install.sh            undo: sudo bash undo.sh            check: see the end of this script
set -eu
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash $0"; exit 1; }
[ -e /dev/watchdog0 ] || { echo "no /dev/watchdog0: the hardware watchdog driver (sp5100_tco) is not loaded"; exit 1; }
id=$(cat /sys/class/watchdog/watchdog0/identity 2> /dev/null || echo unknown)
echo "hardware watchdog: $id"
mkdir -p /etc/systemd/system.conf.d /etc/sysctl.d
# The kernel's values before this script, for undo.sh (kept once, not overwritten by a second run).
O=/etc/sysctl.d/.bc5-panic.before
[ -e "$O" ] || sysctl -e kernel.panic kernel.panic_on_oops kernel.softlockup_panic kernel.hardlockup_panic > "$O"
cat > /etc/systemd/system.conf.d/90-bc5-watchdog.conf << 'EOF'
# BC5 (2026-10-27, the maintainer asked): feed the hardware watchdog; a hung kernel resets the box. Undo: undo.sh
[Manager]
RuntimeWatchdogSec=30s
RebootWatchdogSec=2min
EOF
cat > /etc/sysctl.d/90-bc5-panic.conf << 'EOF'
# BC5 (2026-10-27, the maintainer asked): reboot 10 s after a panic; panic on an oops and on soft/hard lockups,
# so a wedged kernel does not wait forever. Undo: undo.sh
kernel.panic = 10
kernel.panic_on_oops = 1
kernel.softlockup_panic = 1
kernel.hardlockup_panic = 1
EOF
chmod 644 /etc/systemd/system.conf.d/90-bc5-watchdog.conf /etc/sysctl.d/90-bc5-panic.conf
sysctl --load=/etc/sysctl.d/90-bc5-panic.conf > /dev/null
systemctl daemon-reexec
echo "done:"
systemctl show -p RuntimeWatchdogUSec -p RebootWatchdogUSec
sysctl kernel.panic kernel.panic_on_oops kernel.softlockup_panic kernel.hardlockup_panic
echo "check after the next reboot: systemctl show -p RuntimeWatchdogUSec (30s); journalctl -b | grep -i watchdog"
