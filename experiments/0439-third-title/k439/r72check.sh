#!/usr/bin/env bash
# BC5 exp 0439: the display check of LESSONS R72 (2026-11-21: from 13:51 every boot logged "No EDID read" on DP-1 and the
# desktop ran at 640x480@59.94 instead of 1920x1080@60; the boot checks looked only at "connected").
# R72 as amended by the top session (11-21 19:52): the current state decides. Exit 0 when the EDID is non-empty, the first
# listed mode is 1920x1080, and the active mode is 1920x1080@60 at scale 1 (kscreen-doctor -o: the mode marked with '*'
# and its output's "Scale:"). The boot's "No EDID read" lines are counted and recorded, not a failure (a boot's init may log
# one before a replugged monitor answers). Run before every series. A failure is not fixed here: no measurement, report to
# the top session (the monitor or cable needs the maintainer).
# One line on stdout: "display: edid <bytes> B, first mode <m>, active <mode> scale <s>, No EDID read lines <n> (recorded
# only): OK|BAD (<why>)".
#   bash r72check.sh          (on the box, as the maintainer's user; R72_CONN=card1-DP-1 by default)
set -u
C=${R72_CONN:-card1-DP-1}; D=/sys/class/drm/$C
edid=$( { wc -c < "$D/edid"; } 2> /dev/null || echo 0)
first=$(head -1 "$D/modes" 2> /dev/null); first=${first:-none}
noedid=$( (sudo -n dmesg 2> /dev/null || journalctl -k -b 0 --no-pager 2> /dev/null) | grep -c 'No EDID read')
rt=/run/user/$(id -u); wl=$(ls -1 "$rt" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$')
kd=$(XDG_RUNTIME_DIR=$rt WAYLAND_DISPLAY=${wl:-wayland-0} timeout 10 kscreen-doctor -o 2> /dev/null | sed 's/\x1b\[[0-9;]*m//g')
active=$(printf '%s\n' "$kd" | grep -o '[0-9]\+x[0-9]\+@[0-9.]\+\*' | head -1 | tr -d '*')
active=${active:-unknown}
scale=$(printf '%s\n' "$kd" | grep -o 'Scale: [0-9.]\+' | head -1 | sed 's/Scale: //')
scale=${scale:-unknown}
why=""
[ "$edid" -gt 0 ] || why="$why empty EDID;"
[ "$first" = 1920x1080 ] || why="$why first mode $first;"
case "$active" in 1920x1080@60*) ;; *) why="$why active $active;" ;; esac
case "$scale" in 1|1.0|1.00) ;; *) why="$why scale $scale;" ;; esac
line="display: edid $edid B, first mode $first, active $active scale $scale, No EDID read lines $noedid (recorded only)"
if [ -z "$why" ]; then
  echo "$line: OK"
else
  echo "$line: BAD ($why )"
  exit 1
fi
