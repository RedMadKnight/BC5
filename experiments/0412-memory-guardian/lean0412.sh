#!/usr/bin/env bash
# BC5 exp 0412: the lean session for a play (the top session's order, 2026-11-11; README section 30). No root.
# While the emulator runs, the parts of the desktop that hold memory and GPU buffers and are not needed in a game are
# stopped: plasma-plasmashell.service (the panel, the desktop and the notifications: about 170 MiB of memory and
# 174 MiB of GPU memory, README section 18). KWin, PipeWire, the pad's path, sshd and tailscale are not touched.
# Everything stopped is started again when the launcher's process is gone, whatever ended it: a watcher of its own
# (setsid, outside the launcher's process group) waits for that and runs the restore, so a normal exit, the hard
# stop, a crash and a kill of the launcher all end the same way. The state is in <state file>.
#   lean0412.sh dry                    what would be stopped, with its memory now; stops nothing
#   lean0412.sh stop <launcher pid>    stop the units that are active, note them, start the watcher
#   lean0412.sh restore                start the noted units again (the watcher runs this; safe to run by hand, twice)
#   lean0412.sh watch <launcher pid>   (internal) wait until the pid is gone, then restore
set -u
E=$HOME/bc5-work/exp0412; STATE=$E/lean.state; LOG=$E/lean.log
UNITS="plasma-plasmashell.service"
say() { printf '%s lean: %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
case "${1:-}" in
  dry)
    for u in $UNITS; do
      echo "dry: would stop $u (now $(systemctl --user is-active "$u" 2>&1), memory $(( $(systemctl --user show -p MemoryCurrent --value "$u" 2> /dev/null | grep -E '^[0-9]+$' || echo 0) / 1048576 )) MiB) and start it again when the launcher is gone"
    done
    echo "dry: nothing stopped" ;;
  stop)
    PID=${2:?the launcher pid}
    : > "$STATE.new" || exit 1
    for u in $UNITS; do
      if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then echo "$u" >> "$STATE.new"; fi
    done
    mv -fT "$STATE.new" "$STATE" || exit 1
    # The watcher first: if stopping fails half way, the restore still comes.
    (setsid nohup /usr/bin/bash "$0" watch "$PID" > /dev/null 2>&1 < /dev/null &)
    while read -r u; do
      [ -n "$u" ] || continue
      systemctl --user stop "$u" && say "stopped $u" || say "could not stop $u"
    done < "$STATE" ;;
  restore)
    [ -s "$STATE" ] || { say "nothing to restore"; exit 0; }
    while read -r u; do
      [ -n "$u" ] || continue
      if [ "$(systemctl --user is-active "$u" 2> /dev/null)" = active ]; then say "$u is active already"; else
        systemctl --user start "$u" && say "started $u" || say "COULD NOT START $u (by hand: systemctl --user start $u)"
      fi
    done < "$STATE"
    mv -fT "$STATE" "$STATE.done" ;;
  watch)
    PID=${2:?the launcher pid}
    while [ -d "/proc/$PID" ]; do sleep 1; done
    exec /usr/bin/bash "$0" restore ;;
  *) echo "usage: lean0412.sh dry | stop <launcher pid> | restore"; exit 1 ;;
esac
