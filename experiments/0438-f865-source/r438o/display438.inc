# BC5 exp 0438 (LESSONS R72, 2026-11-21): the display part of a clean-boot check. Sourced by ab438o.sh and the smoke
# scripts. On boots c05993c0, c97d43e6 and 7986fd90 the kernel logged "EDID err: 2, on connector: DP-1" / "No EDID read",
# the EDID was empty, the only mode was 640x480@59.94 and every lean series ran in that mode while the old check, which
# read only status = connected, passed. display_check sets DISP (one line for the series header) and returns 0 only if:
#   - a connected DP/HDMI connector has an EDID of more than 0 bytes;
#   - its first mode is 1920x1080;
#   - this boot's kernel log has 0 "No EDID read" lines;
#   - KWin's active mode (kscreen-doctor -o, the mode marked *) is 1920x1080 at 60 Hz (59.9x accepted).
# DISP_DRM (default /sys/class/drm) lets a stand-in test point it elsewhere; kscreen-doctor and sudo come from PATH.
display_check() {
    local d=${DISP_DRM:-/sys/class/drm} c="" s es fm ne am wl
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
    am=$(XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${wl:-wayland-0} kscreen-doctor -o 2> /dev/null | LC_ALL=C tr -d '\033' | sed 's/\[[0-9;]*m//g' | grep -o '[0-9]*x[0-9]*@[0-9.]*\*' | head -1 | tr -d '*')
    DISP="display: ${c##*/} EDID ${es} bytes, first mode ${fm:-none}, No-EDID lines this boot ${ne}, active ${am:-unknown}"
    [ "${es:-0}" -gt 0 ] && [ "$fm" = 1920x1080 ] && [ "$ne" = 0 ] || return 1
    case "$am" in 1920x1080@60* | 1920x1080@59.9*) return 0 ;; *) return 1 ;; esac
}
