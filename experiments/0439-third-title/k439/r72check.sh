#!/usr/bin/env bash
# BC5 exp 0439: the display check of LESSONS R72 (2026-11-21: from 13:51 every boot logged "No EDID read" on DP-1 and the
# desktop ran at 640x480@59.94 instead of 1920x1080@60; the boot checks looked only at "connected").
# One line on stdout: "display: edid <bytes> B, first mode <m>, No EDID read lines <n>, active <mode>: OK|BAD (<why>)".
# Exit 0 when all four hold: EDID non-empty, first listed mode 1920x1080, 0 "No EDID read" lines in this boot's kernel
# log, active mode 1920x1080@60 (kscreen-doctor -o, the mode marked with '*'). A failure is not fixed here: no
# measurement, report to the top session (the monitor or cable needs the maintainer).
#   bash r72check.sh          (on the box, as the maintainer's user; R72_CONN=card1-DP-1 by default)
set -u
C=${R72_CONN:-card1-DP-1}; D=/sys/class/drm/$C
edid=$( { wc -c < "$D/edid"; } 2> /dev/null || echo 0)
first=$(head -1 "$D/modes" 2> /dev/null); first=${first:-none}
noedid=$( (sudo -n dmesg 2> /dev/null || journalctl -k -b 0 --no-pager 2> /dev/null) | grep -c 'No EDID read')
rt=/run/user/$(id -u); wl=$(ls -1 "$rt" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$')
active=$(XDG_RUNTIME_DIR=$rt WAYLAND_DISPLAY=${wl:-wayland-0} timeout 10 kscreen-doctor -o 2> /dev/null | sed 's/\x1b\[[0-9;]*m//g' \
  | grep -o '[0-9]\+x[0-9]\+@[0-9.]\+\*' | head -1 | tr -d '*')
active=${active:-unknown}
why=""
[ "$edid" -gt 0 ] || why="$why empty EDID;"
[ "$first" = 1920x1080 ] || why="$why first mode $first;"
[ "$noedid" -eq 0 ] || why="$why $noedid No EDID read lines;"
case "$active" in 1920x1080@60*) ;; *) why="$why active $active;" ;; esac
if [ -z "$why" ]; then
  echo "display: edid $edid B, first mode $first, No EDID read lines $noedid, active $active: OK"
else
  echo "display: edid $edid B, first mode $first, No EDID read lines $noedid, active $active: BAD ($why )"
  exit 1
fi
