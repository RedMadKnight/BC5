#!/usr/bin/env bash
# BC5 experiment 0164: drive the emulator window on the KDE Wayland session from ssh.
#   drive0164.sh focus            focus the emulator window (KWin script); prints "X Y W H" and the pointer
#   drive0164.sh cursor           print the pointer position "X Y"
#   drive0164.sh moveto X Y       move the pointer to screen X,Y (feedback loop over ydotool)
#   drive0164.sh click            left click
#   drive0164.sh key CODE...      press and release evdev key codes (1=Esc 28=Enter 108=Down 103=Up
#                                 105=Left 106=Right 59=F1 60=F2 87=F11 57=Space)
# Needs ydotoold (setsid ydotoold --socket-path=/run/user/1000/.ydotool_socket &). KWin's print()
# is a disabled log category, so the scripts report through callDBus to org.bc5.Probe, which a
# dbus-monitor writes to $D/probe.log.
set -u
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
D=~/bc5-work/exp0164; mkdir -p "$D"

kwin_run() { # $1 = js file: load, run, stop
  local id
  id=$(dbus-send --print-reply --dest=org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript string:"$1" 2>/dev/null | awk '/int32/{print $2}')
  [ -n "$id" ] || { echo "kwin: loadScript failed" >&2; return 1; }
  dbus-send --print-reply --dest=org.kde.KWin "/Scripting/Script$id" org.kde.kwin.Script.run >/dev/null 2>&1
  sleep 0.3
  dbus-send --print-reply --dest=org.kde.KWin "/Scripting/Script$id" org.kde.kwin.Script.stop >/dev/null 2>&1
}
probe_start() {
  pgrep -f "dbus-monitor --session interface=org.bc5.Probe" >/dev/null && return
  setsid nohup dbus-monitor --session "interface=org.bc5.Probe" > "$D/probe.log" 2>&1 &
  sleep 0.8
}
cursor_read() { # prints "X Y"
  probe_start
  cat > "$D/cursor.js" <<'JS'
callDBus("org.bc5.Probe", "/probe", "org.bc5.Probe", "cursor", workspace.cursorPos.x, workspace.cursorPos.y);
JS
  kwin_run "$D/cursor.js"
  grep -A2 "member=cursor" "$D/probe.log" | tail -n 2 | awk '{printf "%s ", $2}'; echo
}

case ${1:-} in
  focus)
    probe_start
    cat > "$D/focus.js" <<'JS'
var list = workspace.windowList();
for (var i = 0; i < list.length; i++) {
  var w = list[i];
  if (w.caption.indexOf("Source build") >= 0 || w.caption.indexOf("fps:") >= 0) {
    workspace.activeWindow = w;
    var g = w.frameGeometry;
    callDBus("org.bc5.Probe", "/probe", "org.bc5.Probe", "window", g.x, g.y, g.width, g.height);
  }
}
JS
    kwin_run "$D/focus.js"
    grep -A4 "member=window" "$D/probe.log" | tail -n 4 | awk '{printf "%s ", $2}'; echo
    cursor_read ;;
  cursor) cursor_read ;;
  moveto)
    X=$2; Y=$3
    for i in $(seq 1 40); do
      read -r cx cy < <(cursor_read)
      [ -n "${cx:-}" ] || { echo "no cursor position"; exit 1; }
      dx=$((X - cx)); dy=$((Y - cy))
      echo "at $cx,$cy  delta $dx,$dy"
      [ "${dx#-}" -le 2 ] && [ "${dy#-}" -le 2 ] && exit 0
      # small steps keep the pointer below the acceleration threshold
      sx=$(( dx > 150 ? 150 : (dx < -150 ? -150 : dx) )); sy=$(( dy > 150 ? 150 : (dy < -150 ? -150 : dy) ))
      ydotool mousemove -x "$sx" -y "$sy"; sleep 0.15
    done
    echo "did not converge" ;;
  click) ydotool click 0xC0 ;;
  key) shift; for k in "$@"; do ydotool key "$k:1" "$k:0"; sleep 0.25; done ;;
  *) echo "usage: see header"; exit 2 ;;
esac
