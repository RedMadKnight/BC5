#!/usr/bin/env bash
# BC5 experiment 0301, on the laptop: drive the emulator window during run T1 over ssh (exp 0164's drive0164.sh on
# the box: ydotool through ydotoold, a KWin script for the pointer) and take screenshots (spectacle). Every call
# checks first that the box's lock line is this run's, so another session's run is never touched. The screenshots
# stay on the box (~/bc5-work/exp0301/shots/); a copy for looking at goes to $SHOTS on the laptop, outside the repo.
#   drive0301.sh ydotoold-start | ydotoold-stop     start / stop ydotoold (only for T1; stopped right after it)
#   drive0301.sh shot <name>                        a screenshot, copied to $SHOTS/<name>.png
#   drive0301.sh key <evdev code>...                e.g. 59 = F1
#   drive0301.sh click <X> <Y>                      move the pointer to X,Y and click
#   drive0301.sh lines                              the emulator log's host-menu and MangoHud lines so far
# usage: TAG=T1 SHOTS=<laptop dir> drive0301.sh <command> [args]
set -u
TAG=${TAG:-T1}
SHOTS=${SHOTS:-.}
SSH="ssh -o ServerAliveInterval=10 bc250"
G="grep -q '^mangohud exp 0301 | run $TAG ' ~/bc5-work/BOX-LOCK || { echo 'not our run: nothing done'; exit 1; }"
ENV="export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0"
case ${1:-} in
  ydotoold-start)
    $SSH "$G; $ENV; pgrep -x ydotoold > /dev/null || { setsid nohup ydotoold --socket-path=/run/user/1000/.ydotool_socket > ~/bc5-work/exp0301/ydotoold.log 2>&1 < /dev/null & sleep 1; }; pgrep -a -x ydotoold" ;;
  ydotoold-stop)  # no lock check: stopping our own daemon is always allowed
    # the probe's dbus-monitor (drive0164.sh) by PID: a pkill -f pattern would also match this ssh's own shell
    $SSH "pkill -x ydotoold; sleep 0.5; pgrep -a -x ydotoold || echo 'ydotoold stopped'; pgrep -a dbus-monitor | awk '/org.bc5.Probe/ {print \$1}' | xargs -r kill; pgrep -a dbus-monitor | grep -c org.bc5.Probe | sed 's/^/probe monitors left: /'" ;;
  shot)
    $SSH "$G; $ENV; mkdir -p ~/bc5-work/exp0301/shots; spectacle -b -n -f -o ~/bc5-work/exp0301/shots/$2.png > /dev/null 2>&1; ls -la ~/bc5-work/exp0301/shots/$2.png" &&
      mkdir -p "$SHOTS" && scp -q "bc250:bc5-work/exp0301/shots/$2.png" "$SHOTS/$2.png" && echo "copied to $SHOTS/$2.png" ;;
  key) shift; $SSH "$G; ~/bc5-work/drive0164.sh key $*" ;;
  click) $SSH "$G; ~/bc5-work/drive0164.sh moveto $2 $3 | tail -1; ~/bc5-work/drive0164.sh click" ;;
  focus) $SSH "$G; ~/bc5-work/drive0164.sh focus" ;;
  lines) $SSH "grep -a -E 'host menu:|MangoHud' ~/bc5-work/exp0301/play-last.log | tail -20" ;;
  *) echo "usage: see header"; exit 2 ;;
esac
