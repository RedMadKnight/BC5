# BC5 exp 0438 (LESSONS R72, amended 2026-11-21 19:52): the display part of a clean-boot check, run before EVERY run
# (the EDID read can fail again at any reboot). Sourced by ab438o.sh and the smoke scripts. On boots c05993c0, c97d43e6
# and (until the replug) 7986fd90 the kernel logged "No EDID read" on DP-1, the EDID was empty, the only mode was
# 640x480@59.94, and every lean series ran in that mode while the old check, which read only status = connected, passed.
# display_check sets DISP (one line for the header) and returns 0 only if the CURRENT state is right:
#   - a connected DP/HDMI connector has an EDID of more than 0 bytes;
#   - its first mode is 1920x1080;
#   - KWin's active mode (kscreen-doctor -o, the mode marked *) is 1920x1080 at 60 Hz (59.9x accepted), with Scale 1.
# This boot's count of "No EDID read" lines is recorded only: one from the boot's init does not disqualify a display
# whose current state is right.
# DISP_DRM (default /sys/class/drm) lets a stand-in test point it elsewhere; kscreen-doctor and sudo come from PATH.
display_check() {
    local d=${DISP_DRM:-/sys/class/drm} c="" s es fm ne am sc wl ko
    for s in "$d"/card*-DP-*/status "$d"/card*-HDMI-*/status; do
        [ -f "$s" ] && [ "$(cat "$s")" = connected ] && { c=${s%/status}; break; }
    done
    es=0; fm=""
    if [ -n "$c" ]; then
        es=$(wc -c < "$c/edid" 2> /dev/null || echo 0)
        fm=$(head -1 "$c/modes" 2> /dev/null)
    fi
    ne=$(sudo -n dmesg 2> /dev/null | grep -c 'No EDID read')
    wl=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
    ko=$(XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${wl:-wayland-0} kscreen-doctor -o 2> /dev/null | LC_ALL=C tr -d '\033' | sed 's/\[[0-9;]*m//g')
    am=$(printf '%s\n' "$ko" | grep -o '[0-9]*x[0-9]*@[0-9.]*\*' | head -1 | tr -d '*')
    sc=$(printf '%s\n' "$ko" | grep -m1 'Scale:' | awk '{print $2}')
    DISP="display: ${c##*/} EDID ${es} bytes, first mode ${fm:-none}, active ${am:-unknown}, scale ${sc:-unknown}; No-EDID lines this boot ${ne} (recorded only)"
    [ "${es:-0}" -gt 0 ] && [ "$fm" = 1920x1080 ] && [ "$sc" = 1 ] || return 1
    case "$am" in 1920x1080@60* | 1920x1080@59.9*) return 0 ;; *) return 1 ;; esac
}
# the game's presented size, from a run's play log: the port size at its first sceVideoOutGetOutputStatus (exp 0401 line)
game_port_size() { grep -a -m1 -o 'port size [0-9]*x[0-9]*' "$1" 2> /dev/null | awk '{print $3}'; }
